# 演示音频

`scripts/seed_demo.py` 会把本目录的音频复制到 `DATA_DIR/audios/`（已存在同名 `audioId` 的会跳过），文件名即 `audioId`。

| 文件 | 说明 |
|---|---|
| `audio_003.flac` | 真实多人会议录音，约 21 分 13 秒，16kHz，立体声（**A 路在左声道，B 路在右声道**），无损 FLAC（约 38MB，解码后与原 WAV 逐采样一致） |

## 来源

AMI 会议语料（AMI Meeting Corpus）的 ES2002a 会议，英文，一场四人的产品设计会议。语料以 CC BY 许可发布，使用时需要署名；具体条款以 AMI 官方说明为准。

- A 路：`ES2002a.Headset-1.wav`
- B 路：`ES2002a.Headset-3.wav`

同一场会议共有四个头戴麦克风（Headset-0 到 3），选这两路是因为说话最多（另两路几乎不说话）。注意这是**会议**，不是电话，而且麦克风之间有串音（一个麦克风会收到旁边人的声音）。

## 如何重新生成

```bash
BASE=https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/ES2002a/audio
curl -L -o h1.wav $BASE/ES2002a.Headset-1.wav
curl -L -o h3.wav $BASE/ES2002a.Headset-3.wav
ffmpeg -i h1.wav -i h3.wav \
  -filter_complex "[0:a]loudnorm=I=-18:TP=-2[a];[1:a]loudnorm=I=-18:TP=-2[b];[a][b]join=inputs=2:channel_layout=stereo[o]" \
  -map "[o]" -ar 16000 -c:a flac -compression_level 8 audio_003.flac
```

两路各自做了响度归一化（原录音音量很低）。
