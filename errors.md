
====================
RUNNING: Jetson System Stats
====================
--- Jetson Nano System Stats ---
Total CPU Usage: 6.7%
Memory: Total 7.6G, Used 2.3G
Disk: Total 59G, Used 41G (73%)

Attempting to get GPU stats (tegrastats)...
Error checking tegrastats: __init__() got an unexpected keyword argument 'capture_output'

Next: Camera Test. A window will open for 10 seconds. Press 'q' to skip/close.
Press Enter to continue...

====================
RUNNING: Camera Test
====================
--- Testing Camera index 0 ---
[ WARN:0] global /home/soda/opencv/modules/videoio/src/cap_gstreamer.cpp (1759) handleMessage OpenCV | GStreamer warning: Embedded video playback halted; module v4l2src0 reported: Internal data stream error.
[ WARN:0] global /home/soda/opencv/modules/videoio/src/cap_gstreamer.cpp (888) open OpenCV | GStreamer warning: unable to start pipeline
[ WARN:0] global /home/soda/opencv/modules/videoio/src/cap_gstreamer.cpp (480) isPipelinePlaying OpenCV | GStreamer warning: GStreamer: pipeline have not been created
Camera opened successfully. Press 'q' to quit.

(python3:14777): Gtk-WARNING **: 17:10:36.432: Unable to locate theme engine in module_path: "adwaita",

(python3:14777): Gtk-WARNING **: 17:10:36.436: Unable to locate theme engine in module_path: "adwaita",

(python3:14777): Gtk-WARNING **: 17:10:36.438: Unable to locate theme engine in module_path: "murrine",

(python3:14777): Gtk-WARNING **: 17:10:36.439: Unable to locate theme engine in module_path: "murrine",

(python3:14777): Gtk-WARNING **: 17:10:36.439: Unable to locate theme engine in module_path: "murrine",

(python3:14777): Gtk-WARNING **: 17:10:36.444: Unable to locate theme engine in module_path: "murrine",

(python3:14777): Gtk-WARNING **: 17:10:36.445: Unable to locate theme engine in module_path: "murrine",

(python3:14777): Gtk-WARNING **: 17:10:36.445: Unable to locate theme engine in module_path: "murrine",

(python3:14777): Gtk-WARNING **: 17:10:36.447: Unable to locate theme engine in module_path: "murrine",

(python3:14777): Gtk-WARNING **: 17:10:36.448: Unable to locate theme engine in module_path: "murrine",

(python3:14777): Gtk-WARNING **: 17:10:36.449: Unable to locate theme engine in module_path: "murrine",

(python3:14777): Gtk-WARNING **: 17:10:36.449: Unable to locate theme engine in module_path: "murrine",

(python3:14777): Gtk-WARNING **: 17:10:36.449: Unable to locate theme engine in module_path: "murrine",
Camera test finished.

Next: Audio Test. It will record 3 seconds and then play it back.
Press Enter to continue...

====================
RUNNING: Audio Test
====================
ALSA lib confmisc.c:1281:(snd_func_refer) Unable to find definition 'cards.tegra-hda-xnx.pcm.front.0:CARD=0'
ALSA lib conf.c:4528:(_snd_config_evaluate) function snd_func_refer returned error: No such file or directory
ALSA lib conf.c:5007:(snd_config_expand) Evaluate error: No such file or directory
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM front
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM cards.pcm.rear
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM cards.pcm.center_lfe
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM cards.pcm.side
ALSA lib confmisc.c:1281:(snd_func_refer) Unable to find definition 'cards.tegra-hda-xnx.pcm.surround51.0:CARD=0'
ALSA lib conf.c:4528:(_snd_config_evaluate) function snd_func_refer returned error: No such file or directory
ALSA lib conf.c:5007:(snd_config_expand) Evaluate error: No such file or directory
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM surround21
ALSA lib confmisc.c:1281:(snd_func_refer) Unable to find definition 'cards.tegra-hda-xnx.pcm.surround51.0:CARD=0'
ALSA lib conf.c:4528:(_snd_config_evaluate) function snd_func_refer returned error: No such file or directory
ALSA lib conf.c:5007:(snd_config_expand) Evaluate error: No such file or directory
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM surround21
ALSA lib confmisc.c:1281:(snd_func_refer) Unable to find definition 'cards.tegra-hda-xnx.pcm.surround40.0:CARD=0'
ALSA lib conf.c:4528:(_snd_config_evaluate) function snd_func_refer returned error: No such file or directory
ALSA lib conf.c:5007:(snd_config_expand) Evaluate error: No such file or directory
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM surround40
ALSA lib confmisc.c:1281:(snd_func_refer) Unable to find definition 'cards.tegra-hda-xnx.pcm.surround51.0:CARD=0'
ALSA lib conf.c:4528:(_snd_config_evaluate) function snd_func_refer returned error: No such file or directory
ALSA lib conf.c:5007:(snd_config_expand) Evaluate error: No such file or directory
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM surround41
ALSA lib confmisc.c:1281:(snd_func_refer) Unable to find definition 'cards.tegra-hda-xnx.pcm.surround51.0:CARD=0'
ALSA lib conf.c:4528:(_snd_config_evaluate) function snd_func_refer returned error: No such file or directory
ALSA lib conf.c:5007:(snd_config_expand) Evaluate error: No such file or directory
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM surround50
ALSA lib confmisc.c:1281:(snd_func_refer) Unable to find definition 'cards.tegra-hda-xnx.pcm.surround51.0:CARD=0'
ALSA lib conf.c:4528:(_snd_config_evaluate) function snd_func_refer returned error: No such file or directory
ALSA lib conf.c:5007:(snd_config_expand) Evaluate error: No such file or directory
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM surround51
ALSA lib confmisc.c:1281:(snd_func_refer) Unable to find definition 'cards.tegra-hda-xnx.pcm.surround71.0:CARD=0'
ALSA lib conf.c:4528:(_snd_config_evaluate) function snd_func_refer returned error: No such file or directory
ALSA lib conf.c:5007:(snd_config_expand) Evaluate error: No such file or directory
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM surround71
ALSA lib confmisc.c:1281:(snd_func_refer) Unable to find definition 'cards.tegra-hda-xnx.pcm.iec958.0:CARD=0,AES0=4,AES1=130,AES2=0,AES3=2'
ALSA lib conf.c:4528:(_snd_config_evaluate) function snd_func_refer returned error: No such file or directory
ALSA lib conf.c:5007:(snd_config_expand) Evaluate error: No such file or directory
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM iec958
ALSA lib confmisc.c:1281:(snd_func_refer) Unable to find definition 'cards.tegra-hda-xnx.pcm.iec958.0:CARD=0,AES0=4,AES1=130,AES2=0,AES3=2'
ALSA lib conf.c:4528:(_snd_config_evaluate) function snd_func_refer returned error: No such file or directory
ALSA lib conf.c:5007:(snd_config_expand) Evaluate error: No such file or directory
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM spdif
ALSA lib confmisc.c:1281:(snd_func_refer) Unable to find definition 'cards.tegra-hda-xnx.pcm.iec958.0:CARD=0,AES0=4,AES1=130,AES2=0,AES3=2'
ALSA lib conf.c:4528:(_snd_config_evaluate) function snd_func_refer returned error: No such file or directory
ALSA lib conf.c:5007:(snd_config_expand) Evaluate error: No such file or directory
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM spdif
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM cards.pcm.modem
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM cards.pcm.modem
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM cards.pcm.phoneline
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM cards.pcm.phoneline
ALSA lib pcm_dmix.c:990:(snd_pcm_dmix_open) The dmix plugin supports only playback stream
ALSA lib pcm_hw.c:1713:(_snd_pcm_hw_open) Invalid value for card
ALSA lib pcm_hw.c:1713:(_snd_pcm_hw_open) Invalid value for card
ALSA lib pcm_hw.c:1713:(_snd_pcm_hw_open) Invalid value for card
ALSA lib pcm_hw.c:1713:(_snd_pcm_hw_open) Invalid value for card
ALSA lib pcm_dmix.c:1052:(snd_pcm_dmix_open) unable to open slave
--- Testing Audio Capture ---
Recording for 3 seconds...
Recording finished.
Audio saved to test_output.wav

--- Testing Audio Playback ---
Playing back recorded audio...
Playback finished.

All tests completed.