from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
import logic
import os

class LoggerLabel(Label):
    def log(self, text):
        self.text += text + "\n"

class MainApp(App):
    def build(self):
        self.title = "Python Utils APK"
        
        root = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Tab Panel
        tp = TabbedPanel(do_default_tab=False)
        
        # --- TAB 1: PACKER ---
        tab_pack = TabbedPanelItem(text='Packer')
        layout_pack = BoxLayout(orientation='vertical', spacing=10, padding=10)
        self.pack_path = TextInput(hint_text='Path to folder with PNGs', multiline=False)
        self.pack_name = TextInput(hint_text='Target base name (e.g. main_assets)', multiline=False)
        btn_pack = Button(text='Pack to .plist/.ccz', size_hint_y=None, height=50)
        btn_pack.bind(on_press=self.run_pack)
        layout_pack.add(Label(text="Super Packer", font_size=20))
        layout_pack.add(self.pack_path)
        layout_pack.add(self.pack_name)
        layout_pack.add(btn_pack)
        layout_pack.add(BoxLayout()) # Spacer
        tab_pack.add_widget(layout_pack)
        
        # --- TAB 2: UNPACKER ---
        tab_unpack = TabbedPanelItem(text='Unpacker')
        layout_unpack = BoxLayout(orientation='vertical', spacing=10, padding=10)
        self.unpack_path = TextInput(hint_text='Path to .plist file', multiline=False)
        btn_unpack = Button(text='Unpack to folder', size_hint_y=None, height=50)
        btn_unpack.bind(on_press=self.run_unpack)
        layout_unpack.add(Label(text="Improved Unpacker", font_size=20))
        layout_unpack.add(self.unpack_path)
        layout_unpack.add(btn_unpack)
        layout_unpack.add(BoxLayout()) # Spacer
        tab_unpack.add_widget(layout_unpack)
        
        # --- TAB 3: BMFONT ---
        tab_bmf = TabbedPanelItem(text='BMFont')
        layout_bmf = BoxLayout(orientation='vertical', spacing=10, padding=10)
        self.bmf_fnt = TextInput(hint_text='Path to .fnt file', multiline=False)
        self.bmf_img = TextInput(hint_text='Path to .png atlas', multiline=False)
        self.bmf_out = TextInput(hint_text='Output folder', multiline=False)
        btn_bmf = Button(text='Extract Glyphs', size_hint_y=None, height=50)
        btn_bmf.bind(on_press=self.run_bmf)
        layout_bmf.add(Label(text="BMFont Tool", font_size=20))
        layout_bmf.add(self.bmf_fnt)
        layout_bmf.add(self.bmf_img)
        layout_bmf.add(self.bmf_out)
        layout_bmf.add(btn_bmf)
        layout_bmf.add(BoxLayout()) # Spacer
        tab_bmf.add_widget(layout_bmf)
        
        tp.add_widget(tab_pack)
        tp.add_widget(tab_unpack)
        tp.add_widget(tab_bmf)
        
        root.add_widget(tp)
        
        # Log Area
        root.add_widget(Label(text="Log:", size_hint_y=None, height=30, halign='left'))
        scroll = ScrollView(size_hint_y=0.4)
        self.log_label = LoggerLabel(text="", size_hint_y=None, halign='left', valign='top')
        self.log_label.bind(texture_size=self.log_label.setter('size'))
        scroll.add_widget(self.log_label)
        root.add_widget(scroll)
        
        return root

    def run_pack(self, instance):
        path = self.pack_path.text.strip()
        name = self.pack_name.text.strip()
        if path and name:
            self.log_label.log(f"Starting Pack: {path}")
            try:
                logic.super_pack(path, name, logger=self.log_label.log)
            except Exception as e:
                self.log_label.log(f"Error: {str(e)}")
        else:
            self.log_label.log("Error: Please fill all fields")

    def run_unpack(self, instance):
        path = self.unpack_path.text.strip()
        if path:
            self.log_label.log(f"Starting Unpack: {path}")
            try:
                logic.unpack(path, logger=self.log_label.log)
            except Exception as e:
                self.log_label.log(f"Error: {str(e)}")
        else:
            self.log_label.log("Error: Please provide path")

    def run_bmf(self, instance):
        fnt = self.bmf_fnt.text.strip()
        img = self.bmf_img.text.strip()
        out = self.bmf_out.text.strip()
        if fnt and img and out:
            self.log_label.log(f"Starting BMFont Extract: {fnt}")
            try:
                logic.extract_glyphs(fnt, img, out, logger=self.log_label.log)
            except Exception as e:
                self.log_label.log(f"Error: {str(e)}")
        else:
            self.log_label.log("Error: Please fill all fields")

if __name__ == '__main__':
    MainApp().run()
