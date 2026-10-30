# 演示音频

`scripts/seed_demo.py` 会把本目录的 `*.flac` 复制到 `DATA_DIR/audios/`（已存在同名 `audioId` 的会跳过），文件名即 `audioId`。

| 文件 | 说明 |
|---|---|
| `audio_003.flac` | 真实多人会议录音，约 21 分 13 秒，16kHz，立体声（**A 路在左声道，B 路在右声道**），无损 FLAC（约 38MB） |
| `source/ES2002a.Headset-1.flac` | `audio_003` 的 A 路原始录音（未做响度处理），无损 FLAC（约 10MB） |
| `source/ES2002a.Headset-3.flac` | `audio_003` 的 B 路原始录音（未做响度处理），无损 FLAC（约 9MB） |

## 来源

AMI 会议语料（AMI Meeting Corpus）的 ES2002a 会议，英文，一场四人的产品设计会议。语料以 CC BY 许可发布，使用时需要署名；具体条款以 AMI 官方说明为准。

- A 路：`ES2002a.Headset-1`
- B 路：`ES2002a.Headset-3`

同一场会议共有四个头戴麦克风（Headset-0 到 3），选这两路是因为说话最多（另两路几乎不说话，没有放进仓库）。注意这是**会议**，不是电话，而且麦克风之间有串音（一个麦克风会收到旁边人的声音）。

## 原始录音（`source/`）

`source/` 里是从官方下载的原始 WAV 无损压缩成的 FLAC，**解码后与官方 WAV 逐采样一致**。有它们就不需要再去官网下载。需要还原成 WAV：

```bash
ffmpeg -i source/ES2002a.Headset-1.flac ES2002a.Headset-1.wav
```

如果想从官网重新下载原始文件：

```bash
BASE=https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/ES2002a/audio
curl -L -O $BASE/ES2002a.Headset-0.wav   # 还有 Headset-1、2、3
```

## 重新生成 `audio_003.flac`

两路各自做响度归一化（原录音音量很低），再合成立体声。**必须带 `-sample_fmt s16`**，否则 FLAC 编码器会输出 24 位，与已有文件不一致：

```bash
ffmpeg -i source/ES2002a.Headset-1.flac -i source/ES2002a.Headset-3.flac \
  -filter_complex "[0:a]loudnorm=I=-18:TP=-2[a];[1:a]loudnorm=I=-18:TP=-2[b];[a][b]join=inputs=2:channel_layout=stereo[o]" \
  -map "[o]" -ar 16000 -sample_fmt s16 -c:a flac -compression_level 8 audio_003.flac
```

用 ffmpeg 9.0.1 验证过：这样生成的结果与已提交的 `audio_003.flac` 逐采样一致。换其它 ffmpeg 版本时，`loudnorm` 的结果可能有细微差别。
