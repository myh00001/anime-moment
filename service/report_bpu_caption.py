"""One-shot official S100 BPU vision encoder; run with the TROS environment."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ENCODER='SigLip_int16_SmolVLM2_256M_Instruct_S100.hbm'
NODE='/opt/tros/humble/lib/hobot_llamacpp/hobot_llamacpp'

def model_profile():
    root=Path(__file__).resolve().parent/'local-vlm'
    profiles=[('SmolVLM2-500M',root/'smol500-bpu/SigLip_int16_SmolVLM2_500M_Instruct_S100.hbm',
               root/'smol500-bpu/SmolVLM2-500M-Video-Instruct-Q8_0.gguf',171832992,436808704),
              ('SmolVLM2-256M',root/'bpu-report'/ENCODER,
               root/'SmolVLM2-256M-Video-Instruct-Q8_0.gguf',165506728,175056256)]
    for name,encoder,language,encoder_size,language_size in profiles:
        if encoder.is_file() and language.is_file() and encoder.stat().st_size==encoder_size and language.stat().st_size==language_size:
            return {'name':name,'encoder':encoder,'language':language,'size':512}
    return None

def available():
    return Path(NODE).is_file() and model_profile() is not None

def caption(photo,timeout=25):
    import rclpy
    from ai_msgs.msg import PerceptionTargets
    root=Path(__file__).resolve().parent
    profile=model_profile()
    if profile is None:raise RuntimeError('BPU model assets are incomplete')
    import tempfile
    sys.path.insert(0,str(root/'vendor'))
    from report_subject import prepare_subject
    with tempfile.TemporaryDirectory(prefix='report-subject-') as folder:
        view=Path(folder)/'subject.jpg'
        subject=prepare_subject(photo,view,profile['size'],root)
        if not subject['subject_visible']:
            return dict(subject,text='No reliable subject for clothing description.',seconds=0,model=profile['name'])
        image_bytes=view.read_bytes()
    # Keep the temporary original-derived view alive through the one-shot node.
    temporary=tempfile.TemporaryDirectory(prefix='report-bpu-image-')
    view=Path(temporary.name)/'subject.jpg';view.write_bytes(image_bytes)
    def terminate(*_):raise SystemExit('BPU report interrupted')
    rclpy.init()
    signal.signal(signal.SIGTERM,terminate)
    node=rclpy.create_node('festival_report_'+str(os.getpid()))
    topic='/festival_report_'+str(os.getpid());answers=[]
    subscription=node.create_subscription(PerceptionTargets,topic,answers.append,10)
    command=[NODE,'--ros-args','-p','feed_type:=0','-p','model_type:=1',
        '-p','image:='+str(view),'-p','image_type:=0','-p','llm_threads:=4',
        '-p','user_prompt:=Describe only the outer top garment worn by the person, in under 12 words. Do not describe pants, objects, gender or clothing on furniture.',
        '-p','model_file_name:='+str(profile['encoder']),
        '-p','llm_model_name:='+str(profile['language']),
        '-p','ai_msg_pub_topic_name:='+topic,'-p','text_msg_pub_topic_name:='+topic+'_tokens',
        '--log-level','error']
    start=time.monotonic();process=None
    try:
        process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        while not answers:
            if process.poll() is not None:raise RuntimeError('BPU vision node exited')
            if time.monotonic()-start>=timeout:raise TimeoutError('BPU image observation timed out')
            rclpy.spin_once(node,timeout_sec=.05)
        text=' '.join(target.type for target in answers[0].targets)
        for token in ('</s>','<end_of_utterance>','<|im_end|>'):text=text.replace(token,'')
        if len(text.strip())<8:raise ValueError('Empty BPU observation')
        return dict(subject,text=text.strip(),seconds=round(time.monotonic()-start,3),model=profile['name'],
                perfs=[{'type':p.type,'ms':p.time_ms_duration} for p in answers[0].perfs])
    finally:
        if process and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        node.destroy_subscription(subscription);node.destroy_node();rclpy.shutdown();temporary.cleanup()

if __name__=='__main__':
    print(json.dumps(caption(sys.argv[1],float(sys.argv[2]) if len(sys.argv)>2 else 25),ensure_ascii=True))
