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

def available():
    root=Path(__file__).resolve().parent
    return Path(NODE).is_file() and (root/'local-vlm/bpu-report'/ENCODER).is_file()

def caption(photo,timeout=25):
    import rclpy
    from ai_msgs.msg import PerceptionTargets
    root=Path(__file__).resolve().parent
    def terminate(*_):raise SystemExit('BPU report interrupted')
    rclpy.init()
    signal.signal(signal.SIGTERM,terminate)
    node=rclpy.create_node('festival_report_'+str(os.getpid()))
    topic='/festival_report_'+str(os.getpid());answers=[]
    subscription=node.create_subscription(PerceptionTargets,topic,answers.append,10)
    command=[NODE,'--ros-args','-p','feed_type:=0','-p','model_type:=1',
        '-p','image:='+str(Path(photo).resolve()),'-p','image_type:=0','-p','llm_threads:=4',
        '-p','user_prompt:=Describe only clothing colors and body pose of the visible person in one short sentence. Do not guess objects, activities or identity. If no person is visible, say No person visible.',
        '-p','model_file_name:='+str(root/'local-vlm/bpu-report'/ENCODER),
        '-p','llm_model_name:='+str(root/'local-vlm/SmolVLM2-256M-Video-Instruct-Q8_0.gguf'),
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
        return {'text':text.strip(),'seconds':round(time.monotonic()-start,3),
                'perfs':[{'type':p.type,'ms':p.time_ms_duration} for p in answers[0].perfs]}
    finally:
        if process and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        node.destroy_subscription(subscription);node.destroy_node();rclpy.shutdown()

if __name__=='__main__':
    print(json.dumps(caption(sys.argv[1],float(sys.argv[2]) if len(sys.argv)>2 else 25),ensure_ascii=True))
