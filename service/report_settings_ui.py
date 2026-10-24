"""GTK controls for reporter selection and a masked device-local API Key."""
import threading
from gi.repository import Gtk,GLib
from report_secrets import load_key,save_key,validate_key


class ReportControls:
    def __init__(self,player,root):
        self.player=player;self.root=root;self.saved=bool(load_key(root));self.busy=False
        self.widget=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=9)
        self.choice=Gtk.ComboBoxText()
        self.choice.append('local','本地模型 · InternVL3 + Qwen3')
        self.choice.append('deepseek','云端 API · DeepSeek Flash')
        self.choice.set_active_id(player.festival_settings.get('report_provider','local'))
        self.widget.pack_start(self.choice,False,False,0)
        self.cloud=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        self.widget.pack_start(self.cloud,False,False,0)
        note=Gtk.Label(label='云端模式会将本次摄像头原图发送到 DeepSeek；API 按使用量计费。',xalign=0)
        note.set_line_wrap(True);note.set_max_width_chars(28);self.cloud.pack_start(note,False,False,0)
        self.key=Gtk.Entry();self.key.set_visibility(False);self.key.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.key.set_max_length(4096);self.key.set_placeholder_text('已保存，留空保持原 Key' if self.saved else '输入 DeepSeek API Key')
        self.cloud.pack_start(self.key,False,False,0)
        show=Gtk.CheckButton(label='显示正在输入的 Key');show.connect('toggled',lambda button:self.key.set_visibility(button.get_active()))
        self.cloud.pack_start(show,False,False,0)
        buttons=Gtk.Box(spacing=8);self.test=Gtk.Button(label='测试连接');clear=Gtk.Button(label='删除已存 Key')
        self.test.set_tooltip_text('发送少量文本测试 API，不上传摄像头画面')
        buttons.pack_start(self.test,True,True,0);buttons.pack_start(clear,True,True,0);self.cloud.pack_start(buttons,False,False,0)
        self.status=Gtk.Label(label='Key 仅保存在本机，点击下方保存设置后生效。',xalign=0)
        self.status.set_line_wrap(True);self.status.set_max_width_chars(28);self.widget.pack_start(self.status,False,False,0)
        self.cloud.show_all();self.cloud.set_no_show_all(True)
        self.test.connect('clicked',self.test_clicked);clear.connect('clicked',self.clear_clicked)
        self.choice.connect('changed',self.refresh);player.ai_report.connect('toggled',self.refresh);self.refresh()

    def provider(self):return self.choice.get_active_id() or 'local'

    def refresh(self,*_):
        enabled=self.player.ai_report.get_active()
        cloud=self.provider()=='deepseek'
        self.choice.set_sensitive(enabled);self.cloud.set_visible(cloud);self.cloud.set_sensitive(enabled and cloud)
        if not self.busy:self.status.set_text('Key 仅保存在本机，点击下方保存设置后生效。' if cloud else '本地模型无需 API Key。')
        GLib.idle_add(self.player.resize_panel)

    def save(self):
        value=validate_key(self.key.get_text())
        if value:
            save_key(self.root,value);self.saved=True;self.key.set_text('');self.key.set_placeholder_text('已保存，留空保持原 Key')
        if self.provider()=='deepseek' and self.player.ai_report.get_active() and not load_key(self.root):
            message='请先填写 DeepSeek API Key，或改用本地模型'
            self.status.set_text(message);raise ValueError(message)
        self.status.set_text('设置已保存。云端使用 deepseek-flash。' if self.provider()=='deepseek' else '设置已保存，使用本地模型。')

    def clear_clicked(self,*_):
        save_key(self.root,'');self.saved=False;self.key.set_text('');self.key.set_placeholder_text('输入 DeepSeek API Key')
        self.status.set_text('已删除本机保存的 DeepSeek API Key。')

    def test_clicked(self,*_):
        if self.busy:return
        try:
            key=validate_key(self.key.get_text()) or load_key(self.root)
            if not key:raise ValueError('请先输入 API Key')
        except ValueError as error:self.status.set_text(str(error));return
        self.busy=True;self.test.set_sensitive(False);self.status.set_text('正在测试连接，不会上传摄像头画面…')
        def work():
            try:
                from report_cloud import test_connection,CloudError
                message=test_connection(key)
            except CloudError as error:message=error.message
            except Exception:message='连接测试失败，请检查网络和 Key'
            def done():
                self.busy=False;self.test.set_sensitive(True);self.status.set_text(message);return False
            GLib.idle_add(done)
        threading.Thread(target=work,daemon=True).start()


def build_report_controls(player,root):
    controls=ReportControls(player,root);player.report_controls=controls
    return controls.widget
