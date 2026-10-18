"""Generate ASS with a gold active word, chapter tags, and bookend titles."""
import argparse
import json
from pathlib import Path
import re


def stamp(seconds):
    cs = round(float(seconds) * 100)
    return f'{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}'


def escape(text):
    return text.replace('\\', '').replace('{', '').replace('}', '').replace('\n', r'\N')


def generate(timing):
    lines = ['[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 1920', 'PlayResY: 1080',
             'WrapStyle: 0', 'ScaledBorderAndShadow: yes', '', '[V4+ Styles]',
             'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
             'Style: Caption,EB Garamond,48,&H00FFFFFF,&H00FFFFFF,&H00202020,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,160,160,75,1',
             'Style: Tag,EB Garamond,30,&H00C9D8E8,&H00FFFFFF,&H00202020,&H80000000,0,0,0,0,100,100,1,0,1,1,1,7,70,70,55,1',
             'Style: Title,EB Garamond,76,&H00D9E6F1,&H00FFFFFF,&H00202020,&H80000000,0,0,0,0,100,100,2,0,1,2,1,5,80,80,80,1',
             '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    def event(start, end, text, style='Caption', layer=0):
        if end > start:
            lines.append(f'Dialogue: {layer},{stamp(start)},{stamp(end)},{style},,0,0,0,,{text}')
    # Each event holds one active word in gold, then resets it to white.
    # Explicit event intervals preserve the source's pauses (unlike cumulative \k).
    for line in timing['lines']:
        words = line['words']
        for offset in range(0, len(words), 8):
            group = words[offset:offset + 8]
            boundaries = sorted({group[0]['s'], group[-1]['e'],
                                 *(w['s'] for w in group), *(w['e'] for w in group)})
            for start, end in zip(boundaries, boundaries[1:]):
                text = ' '.join((r'{\c&H0049C9EF&}' + escape(w['w']) + r'{\c&H00FFFFFF&}')
                                if w['s'] <= start < w['e'] else escape(w['w']) for w in group)
                event(start, end, text)
        event(line['start'], line['end'], escape(line['id'].replace('_', ' ').upper()), 'Tag', 1)
    first = timing['lines'][0]
    event(0, first['start'], 'LES MISÉRABLES', 'Title')
    last = timing['lines'][-1]
    cut = next((w['s'] for w in last['words'] if re.sub(r'\W', '', w['w']).lower() == 'says'), last['end'])
    event(max(cut, last['end']), timing['duration'], 'To be continued', 'Title', 2)
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--timing', default='data/timing.json')
    parser.add_argument('--out', default='build/captions.ass')
    args = parser.parse_args()
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generate(json.loads(Path(args.timing).read_text(encoding='utf-8'))), encoding='utf-8')
