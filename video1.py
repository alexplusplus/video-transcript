import tkinter as tk
from tkinter import filedialog, messagebox
import vlc
import os
import sys
import logging
from screeninfo import get_monitors
import re
from datetime import timedelta
import json

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("video_player.log"),
        logging.StreamHandler()
    ]
)

DATA_FILE = "video_player_data.json"

class VideoPlayer:
    def __init__(self, master):
        self.slider_update_in_progress = False
        self.master = master
        self.master.title("Main Video Window")
        self.master.geometry("800x600")

        # Initialize VLC player
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()

        # Video frame in main window
        self.video_frame = tk.Frame(self.master, bg="black")
        self.video_frame.pack(fill=tk.BOTH, expand=1)

        # Bind single right-click event for play/pause
        # self.video_frame.bind("<Button-3>", self.toggle_play_pause)
        # self.video_frame.config(cursor="right_ptr")  # Optional: Change cursor to indicate right-click functionality

        # Initialize subtitle variables
        self.left_subtitles = []
        self.right_subtitles = []
        self.left_subtitle_index = 0
        self.right_subtitle_index = 0
        self.is_closed = False  # Flag to handle closure

        # Initialize persistent data
        self.persistent_data = {}
        self.load_persisted_data()

        # Create Controls Window
        self.create_controls_window()

        # Embed VLC Video
        self.embed_video()

        # Bind the close event
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)
        self.controls_window.protocol("WM_DELETE_WINDOW", self.on_close)

        # Update the slider periodically
        self.update_slider()

        # Initialize playback flags
        self.is_fullscreen = False

        # Bind keyboard shortcuts
        self.master.bind('<space>', self.toggle_play_pause)
        self.master.bind('<Left>', lambda event: self.seek_relative(-5))
        self.master.bind('1', lambda event: self.seek_relative(-1))
        self.master.bind('2', lambda event: self.seek_relative(-2))
        self.master.bind('3', lambda event: self.seek_relative(-3))
        self.master.bind('4', lambda event: self.seek_relative(-4))
        self.master.bind('5', lambda event: self.seek_relative(-5))
        self.master.bind('6', lambda event: self.seek_relative(-6))
        self.master.bind('7', lambda event: self.seek_relative(-7))
        self.master.bind('8', lambda event: self.seek_relative(-8))
        self.master.bind('9', lambda event: self.seek_relative(-9))
        self.master.bind('<Right>', lambda event: self.seek_relative(5))
        self.master.bind('+', self.jump_to_next_subtitle)
        

        
        # Add bindings for numeric keys 1-9
        

        # Initialize audio and subtitle stream variables
        self.current_audio_track = -1
        self.current_subtitle_track = -1

    def load_persisted_data(self):
        """
        Load persisted data from the JSON file.
        """
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    self.persistent_data = json.load(f)
                logging.info("Persisted data loaded successfully.")
            except Exception as e:
                logging.error(f"Error loading persisted data: {e}")
                self.persistent_data = {}
        else:
            self.persistent_data = {}

    def save_persisted_data(self):
        """
        Save current video state to the JSON file.
        """
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.persistent_data, f, indent=4)
            logging.info("Persisted data saved successfully.")
        except Exception as e:
            logging.error(f"Error saving persisted data: {e}")

    def load_video(self):
        """
        Load a video file and start playback. Automatically loads associated subtitles
        and resumes playback if the video was opened previously.
        """
        file_path = filedialog.askopenfilename(
            filetypes=[("Video Files", "*.mp4 *.mkv *.avi *.mov")]
        )
        if file_path:
            try:
                # Reset subtitle paths
                self.left_subtitle_path = None
                self.right_subtitle_path = None

                media = self.instance.media_new(file_path)
                self.player.set_media(media)
                self.player.play()
                self.play_pause_btn.config(text="Pause")
                logging.info(f"Playing video: {file_path}")

                # Initialize video length retrieval
                self.length = 0
                self.get_video_length()  # This will handle loading subtitles and seeking

                # After some delay, load audio and subtitle tracks
                self.master.after(1000, self.load_audio_tracks)
                self.master.after(1500, self.load_subtitle_tracks)

            except Exception as e:
                logging.error(f"Error loading video: {e}")
                messagebox.showerror("Error", f"Failed to load video.\n{str(e)}")

    def get_video_length(self):
        """
        Retrieve the length of the currently loaded video.
        This method schedules itself to run repeatedly until a valid length is obtained.
        Once the length is obtained, it proceeds to load subtitles and seek playback.
        """
        try:
            length_ms = self.player.get_length()  # Length in milliseconds
            if length_ms > 0:
                self.length = length_ms / 1000  # Convert to seconds
                logging.info(f"Video length: {self.length} seconds.")

                # Proceed to load subtitles and seek playback
                self.load_persisted_subtitles_and_seek()
            else:
                # Retry after 100 milliseconds if length is not yet available
                self.master.after(100, self.get_video_length)
        except Exception as e:
            logging.error(f"Error getting video length: {e}")
            self.length = 0

    def load_persisted_subtitles_and_seek(self):
        """
        Load associated subtitles and seek to the last playback position if available.
        Also restore audio and subtitle stream selections.
        """
        try:
            # Get the current video path in absolute form
            media = self.player.get_media()
            if not media:
                logging.warning("No media is currently loaded.")
                return

            video_path = media.get_mrl()
            if video_path.startswith("file://"):
                video_path = video_path[7:]  # Remove 'file://' prefix
            video_path = os.path.abspath(video_path)

            # Check if there's persisted data for this video
            video_data = self.persistent_data.get(video_path)
            if video_data:
                left_sub_path = video_data.get('left_subtitle')
                right_sub_path = video_data.get('right_subtitle')
                last_time = video_data.get('last_playback_time', 0)
                self.current_audio_track = video_data.get('audio_track', -1)
                self.current_subtitle_track = video_data.get('subtitle_track', -1)

                # Automatically load subtitles if paths exist
                if left_sub_path and os.path.exists(left_sub_path):
                    self.left_subtitles = self.load_subtitle_file(left_sub_path)
                    self.left_subtitle_text.config(state=tk.NORMAL)
                    self.left_subtitle_text.delete(1.0, tk.END)
                    self.left_subtitle_text.insert(tk.END, "\n\n".join([s['content'] for s in self.left_subtitles]))
                    self.left_subtitle_text.config(state=tk.DISABLED)
                    self.left_subtitle_path = os.path.abspath(left_sub_path)
                    logging.info(f"Left subtitles loaded from {left_sub_path}")
                else:
                    if left_sub_path:
                        logging.warning(f"Left subtitle file not found: {left_sub_path}")
                        messagebox.showwarning("Warning", f"Left subtitle file not found: {left_sub_path}")

                if right_sub_path and os.path.exists(right_sub_path):
                    self.right_subtitles = self.load_subtitle_file(right_sub_path)
                    self.right_subtitle_text.config(state=tk.NORMAL)
                    self.right_subtitle_text.delete(1.0, tk.END)
                    self.right_subtitle_text.insert(tk.END, "\n\n".join([s['content'] for s in self.right_subtitles]))
                    self.right_subtitle_text.config(state=tk.DISABLED)
                    self.right_subtitle_path = os.path.abspath(right_sub_path)
                    logging.info(f"Right subtitles loaded from {right_sub_path}")
                else:
                    if right_sub_path:
                        logging.warning(f"Right subtitle file not found: {right_sub_path}")
                        messagebox.showwarning("Warning", f"Right subtitle file not found: {right_sub_path}")

                # Resume playback from last saved time
                if last_time > 0:
                    # Ensure that seeking happens after a short delay to allow playback to stabilize
                    self.master.after(500, lambda: self.seek_to_time(last_time))

                # Restore audio and subtitle tracks after a delay
                self.master.after(1000, self.restore_audio_and_subtitle_tracks)

        except Exception as e:
            logging.error(f"Error loading persisted subtitles and seeking playback: {e}")

    def restore_audio_and_subtitle_tracks(self):
        """
        Restore the saved audio and subtitle track selections.
        """
        try:
            if self.current_audio_track != -1:
                self.player.audio_set_track(self.current_audio_track)
                self.audio_var.set(self.current_audio_track)
                logging.info(f"Restored audio track: {self.current_audio_track}")

            if self.current_subtitle_track != -1:
                self.player.video_set_spu(self.current_subtitle_track)
                self.subtitle_var.set(self.current_subtitle_track)
                logging.info(f"Restored subtitle track: {self.current_subtitle_track}")
        except Exception as e:
            logging.error(f"Error restoring audio and subtitle tracks: {e}")

    def seek_to_time(self, seconds):
        """
        Seek the video to the specified time in seconds.
        """
        try:
            # VLC expects time in milliseconds
            self.player.set_time(int(seconds * 1000))
            logging.info(f"Resumed playback from {seconds} seconds.")
        except Exception as e:
            logging.error(f"Error seeking to time {seconds}: {e}")
            messagebox.showerror("Error", f"Failed to seek to the last playback time.\n{str(e)}")

    def load_subtitle_file(self, file_path):
        """
        Load subtitles from a given SRT file.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            subtitles = self.parse_srt(content)
            return subtitles
        except Exception as e:
            logging.error(f"Error loading subtitle file {file_path}: {e}")
            messagebox.showerror("Error", f"Failed to load subtitle file.\n{str(e)}")
            return []

    def create_controls_window(self):
        """
        Create the Controls window with playback controls and audio stream options.
        """
        self.controls_window = tk.Toplevel(self.master)
        self.controls_window.title("Controls")
        self.controls_window.geometry("1100x550")
        self.controls_window.resizable(True, True)
        self.controls_window.bind("<Button-3>", self.toggle_play_pause)

        self.controls_window.bind('<space>', self.toggle_play_pause)
        self.controls_window.bind('<Left>', lambda event: self.seek_relative(-5))
        self.controls_window.bind('<Right>', lambda event: self.seek_relative(5))
        self.controls_window.bind('1', lambda event: self.seek_relative(-1))
        self.controls_window.bind('2', lambda event: self.seek_relative(-2))
        self.controls_window.bind('3', lambda event: self.seek_relative(-3))
        self.controls_window.bind('4', lambda event: self.seek_relative(-4))
        self.controls_window.bind('5', lambda event: self.seek_relative(-5))
        self.controls_window.bind('6', lambda event: self.seek_relative(-6))
        self.controls_window.bind('7', lambda event: self.seek_relative(-7))
        self.controls_window.bind('8', lambda event: self.seek_relative(-8))
        self.controls_window.bind('9', lambda event: self.seek_relative(-9))
        self.controls_window.bind('+', lambda event: self.jump_to_next_subtitle)
        


        # Subtitle Sections Frame
        subtitle_frame = tk.Frame(self.controls_window)
        subtitle_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # Left Subtitle Section
        left_subtitle_frame = tk.LabelFrame(subtitle_frame, text="Subtitles 1")
        left_subtitle_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        self.left_subtitle_text = tk.Text(left_subtitle_frame, height=15, width=40, wrap=tk.WORD, font=("Arial", 14))
        self.left_subtitle_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        self.left_subtitle_btn = tk.Button(left_subtitle_frame, text="Select SRT File", command=lambda: self.load_subtitles('left'))
        self.left_subtitle_btn.pack(pady=5)

        # Right Subtitle Section
        right_subtitle_frame = tk.LabelFrame(subtitle_frame, text="Subtitles 2")
        right_subtitle_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

        self.right_subtitle_text = tk.Text(right_subtitle_frame, height=15, width=40, wrap=tk.WORD, font=("Arial", 14))
        self.right_subtitle_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        self.right_subtitle_btn = tk.Button(right_subtitle_frame, text="Select SRT File", command=lambda: self.load_subtitles('right'))
        self.right_subtitle_btn.pack(pady=5)

        subtitle_frame.columnconfigure(0, weight=1)
        subtitle_frame.columnconfigure(1, weight=1)

        # Control Buttons Frame
        buttons_frame = tk.Frame(self.controls_window)
        buttons_frame.grid(row=1, column=0, padx=10, pady=10, sticky="w")

        # Play/Pause Button
        self.play_pause_btn = tk.Button(buttons_frame, text="Play", command=self.play_pause)
        self.play_pause_btn.grid(row=0, column=0, padx=5)

        # Load Video Button
        load_btn = tk.Button(buttons_frame, text="Load Video", command=self.load_video)
        load_btn.grid(row=0, column=1, padx=5)

        # Fullscreen Button
        self.fullscreen_btn = tk.Button(buttons_frame, text="Fullscreen", command=self.toggle_fullscreen)
        self.fullscreen_btn.grid(row=0, column=2, padx=5)

        # Audio Streams Frame
        audio_frame = tk.LabelFrame(self.controls_window, text="Audio Streams")
        audio_frame.grid(row=1, column=0, padx=10, pady=10, sticky="e")

        self.audio_var = tk.IntVar()
        self.audio_var.set(-1)  # Default to 'Disable' if applicable

        # Arrange audio stream radio buttons horizontally
        self.audio_frame_inner = tk.Frame(audio_frame)
        self.audio_frame_inner.pack(anchor=tk.W)

        # ---- New Subtitle Streams Section ----
        subtitle_stream_frame = tk.LabelFrame(self.controls_window, text="Subtitle Streams")
        subtitle_stream_frame.grid(row=2, column=0, padx=10, pady=10, sticky="w")

        self.subtitle_var = tk.IntVar()
        self.subtitle_var.set(-1)  # Default to 'Disable' if applicable

        # Arrange subtitle stream radio buttons horizontally
        self.subtitle_frame_inner = tk.Frame(subtitle_stream_frame)
        self.subtitle_frame_inner.pack(anchor=tk.W)

        # Load Subtitle Streams Button
        self.load_subtitle_streams_btn = tk.Button(subtitle_stream_frame, text="Refresh Subtitle Streams", command=self.load_subtitle_tracks)
        self.load_subtitle_streams_btn.pack(pady=5)

        # Seek and Volume Sliders Frame
        middle_frame = tk.Frame(self.controls_window)
        middle_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=10)

        # Time Slider
        self.seek_var = tk.StringVar()
        self.time_slider = tk.Scale(
            middle_frame,
            from_=0,
            to=1000,
            orient=tk.HORIZONTAL,
            length=400,
            command=self.seek,
            variable=self.seek_var
        )
        self.time_slider.grid(row=0, column=0, sticky="ew", padx=5)

        # Volume Slider
        self.volume_var = tk.StringVar()
        self.volume_slider = tk.Scale(
            middle_frame,
            from_=0,
            to=200,
            orient=tk.HORIZONTAL,
            command=self.set_volume,
            variable=self.volume_var
        )
        self.volume_slider.set(95)
        self.volume_slider.grid(row=0, column=1, sticky="w", padx=5)

        # Playback Time Label
        self.time_label = tk.Label(self.controls_window, text="00:00:00 / 00:00:00")
        self.time_label.grid(row=4, column=0, columnspan=2, pady=5)

    def embed_video(self):
        """
        Embed the VLC video in the Tkinter frame.
        """
        try:
            if sys.platform.startswith('linux'):  # for Linux using the X Server
                self.player.set_xwindow(self.video_frame.winfo_id())
            elif sys.platform == "win32":  # for Windows
                self.player.set_hwnd(self.video_frame.winfo_id())
            elif sys.platform == "darwin":  # for MacOS
                try:
                    from ctypes import c_void_p
                    self.player.set_nsobject(c_void_p(self.video_frame.winfo_id()))
                except Exception as e:
                    logging.error(f"Error embedding video on MacOS: {e}")
                    messagebox.showerror("Error", f"Failed to embed video on MacOS.\n{str(e)}")
            else:
                messagebox.showerror("Error", "Unsupported OS.")
        except Exception as e:
            logging.error(f"Error embedding video: {e}")
            messagebox.showerror("Error", f"Failed to embed video.\n{str(e)}")

    def load_audio_tracks(self):
        """
        Load available audio tracks and create radio buttons for selection.
        """
        try:
            descs = self.player.audio_get_track_description()
            if descs:
                # Clear existing radio buttons
                for widget in self.audio_frame_inner.winfo_children():
                    widget.destroy()

                # Add 'Disable' option if applicable
                # Uncomment the following lines if 'Disable' is supported
                # tk.Radiobutton(self.audio_frame_inner, text="Disable", variable=self.audio_var, value=-1, command=self.set_audio_track).pack(side=tk.LEFT, padx=5)

                # Dynamically create radio buttons based on available audio tracks
                for track in descs:
                    impl, name = track
                    tk.Radiobutton(self.audio_frame_inner, text=name, variable=self.audio_var, value=impl, command=self.set_audio_track).pack(side=tk.LEFT, padx=5)
                logging.info("Audio tracks loaded.")
            else:
                logging.info("No audio tracks available.")
                messagebox.showinfo("Info", "No audio tracks available.")
        except Exception as e:
            logging.error(f"Error loading audio tracks: {e}")
            messagebox.showerror("Error", f"Failed to load audio tracks.\n{str(e)}")

    def set_audio_track(self):
        """
        Set the VLC player to use the selected audio track.
        """
        try:
            selected_track = self.audio_var.get()
            if selected_track == -1:
                self.player.audio_set_track(-1)  # Disable audio
                logging.info("Audio disabled.")
            else:
                self.player.audio_set_track(selected_track)
                logging.info(f"Audio track set to: {selected_track}")
            self.current_audio_track = selected_track  # Update the current audio track
        except Exception as e:
            logging.error(f"Error setting audio track: {e}")
            messagebox.showerror("Error", f"Failed to set audio track.\n{str(e)}")

    def toggle_fullscreen(self):
        """
        Toggle fullscreen mode via Tkinter's window attributes.
        """
        try:
            if not self.is_fullscreen:
                self.move_to_same_screen()
            self.is_fullscreen = not self.is_fullscreen
            self.master.attributes("-fullscreen", self.is_fullscreen)
            # Update the button text accordingly
            self.fullscreen_btn.config(text="Windowed" if self.is_fullscreen else "Fullscreen")
            logging.info(f"Fullscreen {'enabled' if self.is_fullscreen else 'disabled'}.")
        except Exception as e:
            logging.error(f"Error toggling fullscreen: {e}")
            messagebox.showerror("Error", f"Failed to toggle fullscreen.\n{str(e)}")

    def move_to_same_screen(self):
        """
        Ensure the main window is on the same screen as the controls window before fullscreen.
        """
        try:
            # Get the position of the controls window
            controls_x = self.controls_window.winfo_x()
            controls_y = self.controls_window.winfo_y()

            # Get monitor info
            monitors = get_monitors()
            target_monitor = None
            for monitor in monitors:
                if (monitor.x <= controls_x <= monitor.x + monitor.width) and \
                   (monitor.y <= controls_y <= monitor.y + monitor.height):
                    target_monitor = monitor
                    break

            if target_monitor:
                # Move main window to the same monitor
                self.master.geometry(f"+{target_monitor.x}+{target_monitor.y}")
                logging.info(f"Moved main window to monitor at ({target_monitor.x}, {target_monitor.y}).")
            else:
                logging.warning("Controls window is not on any detected monitor.")
        except Exception as e:
            logging.error(f"Error moving window to the same screen: {e}")

    def toggle_play_pause(self, event=None):
        """
        Toggle between play and pause states.
        Can be called by the space bar or the play/pause button.
        """
        if self.player.is_playing():
            self.player.pause()
            self.play_pause_btn.config(text="Play")
            logging.info("Playback paused.")
        else:
            self.player.play()
            self.play_pause_btn.config(text="Pause")
            logging.info("Playback started.")

    def play_pause(self):
        """
        Existing play/pause method for the button.
        Now just calls toggle_play_pause for consistency.
        """
        self.toggle_play_pause()

    def seek_relative(self, offset):
        """
        Seek relative to the current position.
        :param offset: Time offset in seconds (positive for forward, negative for backward)
        """
        try:
            self.slider_update_in_progress = True
            current_time = self.player.get_time()
            new_time = max(0, current_time + (offset * 1000))  # Convert to milliseconds
            self.player.set_time(int(new_time))
            self.slider_update_in_progress = False
            logging.info(f"Seeked {'forward' if offset > 0 else 'backward'} by {abs(offset)} seconds.")
        except Exception as e:
            logging.error(f"Error seeking relative: {e}")
            messagebox.showerror("Error", f"Failed to seek relative.\n{str(e)}")

    def seek(self, value):
        """
        Seek to a specific position in the video based on the slider.
        """
        try:
            if self.player.is_playing() and not self.slider_update_in_progress:
                length = self.player.get_length()
                seek_time = (float(value) / 1000.0) * length
                self.player.set_time(int(seek_time))
                logging.info(f"Seeking to: {seek_time} ms")
        except Exception as e:
            logging.error(f"Error seeking video: {e}")
            messagebox.showerror("Error", f"Failed to seek video.\n{str(e)}")

    def set_volume(self, volume):
        """
        Set the player's volume based on the slider.
        """
        try:
            volume = int(volume)
            self.player.audio_set_volume(volume)
            logging.info(f"Volume set to: {volume}")
        except Exception as e:
            logging.error(f"Error setting volume: {e}")
            messagebox.showerror("Error", f"Failed to set volume.\n{str(e)}")

    def update_slider(self):
        """
        Update the time slider based on the current playback position.
        """
        if self.is_closed:
            return  # Exit if the window has been closed

        try:
            if self.player.is_playing():
                current_time = self.player.get_time()  # in milliseconds
                length = self.player.get_length()  # in milliseconds
                if length > 0:
                    position = (current_time / length) * 1000
                    self.time_slider.set(int(position))
                    self.update_time_label()
        except Exception as e:
            logging.error(f"Error updating slider: {e}")

        # Schedule the next update
        if not self.is_closed:
            self.master.after(500, self.update_slider)
        self.update_subtitles()  # Update subtitles along with the slider

    def update_time_label(self):
        """
        Update the playback time label.
        """
        try:
            if self.length > 0:
                current_time = self.player.get_time()  # in milliseconds
                length = self.length
                current_sec = int(current_time / 1000)
                total_sec = int(length)
                current_str = self.seconds_to_time(current_sec)
                total_str = self.seconds_to_time(total_sec)
                self.time_label.config(text=f"{current_str} / {total_str}")
            else:
                self.time_label.config(text="00:00:00 / 00:00:00")
        except Exception as e:
            logging.error(f"Error updating time label: {e}")

    @staticmethod
    def seconds_to_time(seconds):
        """
        Convert seconds to HH:MM:SS format.
        """
        hrs = seconds // 3600
        mins = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{int(hrs):02}:{int(mins):02}:{int(secs):02}"

    def on_close(self):
        """
        Handle closing of the application. Persist current video state.
        """
        self.is_closed = True  # Set the flag to True when closing
        try:
            if self.player:
                media = self.player.get_media()
                if not media:
                    logging.warning("No media is currently loaded.")
                else:
                    video_path = media.get_mrl()
                    if video_path.startswith("file://"):
                        video_path = video_path[7:]  # Remove 'file://' prefix
                    video_path = os.path.abspath(video_path)

                    # Get current playback time in seconds
                    current_time = self.player.get_time() / 1000 if self.player.get_time() > 0 else 0

                    # Get subtitle file paths
                    left_sub_path = getattr(self, 'left_subtitle_path', None)
                    right_sub_path = getattr(self, 'right_subtitle_path', None)

                    # Update persistent data
                    self.persistent_data[video_path] = {
                        'left_subtitle': left_sub_path,
                        'right_subtitle': right_sub_path,
                        'last_playback_time': current_time,
                        'audio_track': self.current_audio_track,
                        'subtitle_track': self.current_subtitle_track
                    }

                    self.save_persisted_data()
                    logging.info(f"Persisted state for {video_path} saved at {current_time} seconds.")

                    self.player.stop()
                    logging.info("Video player stopped.")
        except Exception as e:
            logging.error(f"Error during on_close: {e}")
        self.master.destroy()

    def load_subtitles(self, section):
        file_path = filedialog.askopenfilename(filetypes=[("SRT Files", "*.srt")])
        if file_path:
            try:
                subtitles = self.load_subtitle_file(file_path)
                if section == 'left':
                    self.left_subtitles = subtitles
                    self.left_subtitle_index = 0
                    self.left_subtitle_path = os.path.abspath(file_path)  # Track left subtitle path
                else:
                    self.right_subtitles = subtitles
                    self.right_subtitle_index = 0
                    self.right_subtitle_path = os.path.abspath(file_path)  # Track right subtitle path
                logging.info(f"Loaded subtitles for {section} section: {file_path}")
                self.update_subtitles()
            except Exception as e:
                logging.error(f"Error loading subtitles: {e}")
                messagebox.showerror("Error", f"Failed to load subtitles.\n{str(e)}")

    @staticmethod
    def parse_srt(content):
        pattern = re.compile(r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n((?:.*\n)*?)(?:\n|$)')
        subtitles = []
        for match in pattern.finditer(content):
            start = VideoPlayer.parse_time(match.group(2))
            end = VideoPlayer.parse_time(match.group(3))
            text = match.group(4).strip()
            subtitles.append({'start': start, 'end': end, 'content': text})
        return subtitles

    @staticmethod
    def parse_time(time_str):
        h, m, s = time_str.replace(',', '.').split(':')
        return timedelta(hours=int(h), minutes=int(m), seconds=float(s)).total_seconds()

    def update_subtitles(self):
        if self.is_closed or not self.player.is_playing():
            return  # Exit if the window has been closed or video is not playing

        try:
            current_time = self.player.get_time() / 1000  # Convert to seconds

            self.update_subtitle_section(current_time, self.left_subtitles, self.left_subtitle_text, 'left')
            self.update_subtitle_section(current_time, self.right_subtitles, self.right_subtitle_text, 'right')
        except Exception as e:
            logging.error(f"Error updating subtitles: {e}")

        # Schedule the next update
        if not self.is_closed:
            self.master.after(100, self.update_subtitles)

    def update_subtitle_section(self, current_time, subtitles, text_widget, section):
        if not subtitles:
            return

        try:
            current_subtitle = None
            current_index = 0
            for i, subtitle in enumerate(subtitles):
                if subtitle['start'] <= current_time <= subtitle['end']:
                    current_subtitle = subtitle
                    current_index = i
                    break

            if current_subtitle:
                prev_subtitles = subtitles[max(0, current_index - 3):current_index]
                next_subtitles = subtitles[current_index + 1:current_index + 3]

                text_widget.config(state=tk.NORMAL)  # Enable editing
                text_widget.delete(1.0, tk.END)

                # Insert previous subtitles
                for s in prev_subtitles:
                    text_widget.insert(tk.END, s['content'] + "\n\n")

                # Insert current subtitle (will be underlined later)
                current_start = text_widget.index(tk.END)
                text_widget.insert(tk.END, current_subtitle['content'] + "\n\n")
                current_end = text_widget.index(tk.END + "-1c")  # End of the current subtitle

                # Insert next subtitles
                for s in next_subtitles:
                    text_widget.insert(tk.END, s['content'] + "\n\n")

                # Apply underline to current subtitle
                text_widget.tag_remove("underline", "1.0", tk.END)  # Remove previous underlines
                text_widget.tag_add("underline", current_start, current_end)
                text_widget.tag_configure("underline", underline=True)

                # Ensure the current subtitle is visible
                text_widget.see(current_start)

                text_widget.config(state=tk.DISABLED)  # Disable editing

            if section == 'left':
                self.left_subtitle_index = current_index
            else:
                self.right_subtitle_index = current_index

        except Exception as e:
            logging.error(f"Error updating {section} subtitle section: {e}")

    # ---- New Methods for Subtitle Stream Selection ----

    def load_subtitle_tracks(self):
        """
        Load available subtitle tracks from the currently opened video and create radio buttons for selection.
        """
        try:
            descs = self.player.video_get_spu_description()
            if descs:
                # Clear existing subtitle radio buttons
                for widget in self.subtitle_frame_inner.winfo_children():
                    widget.destroy()

                # Add 'Disable' option
                tk.Radiobutton(
                    self.subtitle_frame_inner,
                    text="Disable",
                    variable=self.subtitle_var,
                    value=-1,
                    command=self.set_subtitle_track
                ).pack(side=tk.LEFT, padx=5)

                # Dynamically create radio buttons based on available subtitle tracks
                for spu in descs:
                    id_, description = spu
                    tk.Radiobutton(
                        self.subtitle_frame_inner,
                        text=description if description else f"Subtitle {id_}",
                        variable=self.subtitle_var,
                        value=id_,
                        command=self.set_subtitle_track
                    ).pack(side=tk.LEFT, padx=5)
                logging.info("Subtitle streams loaded.")
            else:
                logging.info("No subtitle streams available.")
                messagebox.showinfo("Info", "No subtitle streams available.")
        except Exception as e:
            logging.error(f"Error loading subtitle streams: {e}")
            messagebox.showerror("Error", f"Failed to load subtitle streams.\n{str(e)}")

    def set_subtitle_track(self):
        """
        Set the VLC player to use the selected subtitle track.
        """
        try:
            selected_spu = self.subtitle_var.get()
            if selected_spu == -1:
                self.player.video_set_spu(-1)  # Disable subtitles
                logging.info("Subtitles disabled.")
            else:
                self.player.video_set_spu(selected_spu)
                logging.info(f"Subtitle track set to: {selected_spu}")
            self.current_subtitle_track = selected_spu  # Update the current subtitle track
        except Exception as e:
            logging.error(f"Error setting subtitle track: {e}")
            messagebox.showerror("Error", f"Failed to set subtitle track.\n{str(e)}")

    def update_subtitle_tracks_ui(self):
        """
        Refresh the subtitle tracks UI elements if needed.
        """
        self.load_subtitle_tracks()

    def rewind_seconds(self, seconds):
        """
        Rewind the video by the specified number of seconds.
        
        Args:
            seconds (int): Number of seconds to rewind
        """
        try:
            current_time = self.player.get_time()  # Current time in milliseconds
            new_time = max(0, current_time - (seconds * 1000))  # Ensure we don't go below 0
            self.player.set_time(int(new_time))
            logging.info(f"Rewound video by {seconds} seconds")
        except Exception as e:
            logging.error(f"Error rewinding video: {e}")
            messagebox.showerror("Error", f"Failed to rewind video.\n{str(e)}")

    def jump_to_next_subtitle(self, event=None):
        """
        Jump to the beginning of the next subtitle fragment in left_subtitles.
        """
        try:
            if not self.left_subtitles:
                logging.info("No left subtitles loaded to jump to")
                return

            current_time = self.player.get_time() / 1000  # Convert to seconds
            next_subtitle = None

            # Find the next subtitle that starts after current time
            for subtitle in self.left_subtitles:
                if subtitle['start'] > current_time:
                    next_subtitle = subtitle
                    break

            if next_subtitle:
                # Jump to the start time of the next subtitle
                self.player.set_time(int(next_subtitle['start'] * 1000)-500)
                logging.info(f"Jumped to next subtitle at {next_subtitle['start']} seconds")
            else:
                logging.info("No next subtitle found")

        except Exception as e:
            logging.error(f"Error jumping to next subtitle: {e}")
            messagebox.showerror("Error", f"Failed to jump to next subtitle.\n{str(e)}")


if __name__ == "__main__":
    try:
        root = tk.Tk()
        player = VideoPlayer(root)
        root.mainloop()
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}")
        messagebox.showerror("Critical Error", f"An unexpected error occurred:\n{str(e)}")