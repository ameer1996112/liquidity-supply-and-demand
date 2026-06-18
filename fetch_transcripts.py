import sys
from youtube_transcript_api import YouTubeTranscriptApi

videos = [
    ("zglv2r9xXnE", "video1.txt"),
    ("kxh_3__oAqg", "video2.txt"),
    ("E5EBc1MtiXQ", "video3.txt"),
    ("LCydpj3CaHo", "video4.txt"),
    ("mRheKDk5EFI", "video5.txt")
]

for vid, fname in videos:
    try:
        transcript_list = YouTubeTranscriptApi.list(vid)
        transcript = transcript_list.find_transcript(['en'])
        data = transcript.fetch()
        text = ' '.join([t['text'] for t in data])
        with open(fname, 'w') as f:
            f.write(text)
        print(f"Saved {fname}")
    except Exception as e:
        print(f"Error fetching {vid}: {e}")
