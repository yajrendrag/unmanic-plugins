#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Decode bitmap subtitle streams into two-colour images for OCR.

    Each decoder produces a list of events:
        {'start': ms, 'end': ms or None,
         'images': [{'x': int, 'y': int, 'width': int, 'height': int, 'rows': [...]}, ...]}
    Each entry of 'rows' is a list of (value, run_length) runs, where value 1 is text
    and value 0 is background.

    Supported codecs:
        hdmv_pgs_subtitle - Blu-ray PGS (copied to a .sup file with ffmpeg, then parsed)
        dvd_subtitle      - DVD / VobSub (packets read with ffprobe)
"""
import json
import os
import struct
import subprocess


class BitmapSubtitleError(Exception):
    pass


def _merge_runs(runs):
    """Merge neighbouring runs that have the same value."""
    merged = []
    for value, length in runs:
        if merged and merged[-1][0] == value:
            merged[-1] = (value, merged[-1][1] + length)
        else:
            merged.append((value, length))
    return merged


def _has_text(rows):
    return any(value for runs in rows for value, _ in runs)


# --------------------------------------------------------------------------------------------
# ffprobe packet reading
# --------------------------------------------------------------------------------------------

def parse_hexdump(dump):
    """
    Convert ffprobe's '-show_data' hexdump text back into bytes.

    Lines look like: '00000000: 0f86 0f67 0000 1c31 ...  ...g...1'

    :param dump: Hexdump string
    :return: bytes
    """
    data = bytearray()
    for line in (dump or '').splitlines():
        if len(line) < 10 or line[8:10] != ': ':
            continue
        data.extend(bytes.fromhex(line[10:50].replace(' ', '')))
    return bytes(data)


def read_stream_packets(file_in, stream_index, timeout=600):
    """
    Read all packets of one stream using ffprobe.

    :param file_in: Path to the media file
    :param stream_index: Absolute stream index
    :param timeout: Seconds before giving up
    :return: Tuple of (extradata bytes, list of packet dicts with 'pts', 'duration', 'data')
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', str(stream_index),
        '-show_streams',
        '-show_packets',
        '-show_data',
        '-of', 'json',
        file_in,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise BitmapSubtitleError(f"ffprobe failed: {result.stderr.strip()}")

    info = json.loads(result.stdout)
    streams = info.get('streams', [])
    extradata = parse_hexdump(streams[0].get('extradata', '')) if streams else b''

    packets = []
    for pkt in info.get('packets', []):
        pts_time = pkt.get('pts_time', pkt.get('dts_time'))
        if pts_time in (None, 'N/A'):
            continue
        duration_time = pkt.get('duration_time')
        packets.append({
            'pts': float(pts_time) * 1000,
            'duration': float(duration_time) * 1000 if duration_time not in (None, 'N/A') else 0,
            'data': parse_hexdump(pkt.get('data', '')),
        })
    packets.sort(key=lambda p: p['pts'])
    return extradata, packets


# --------------------------------------------------------------------------------------------
# DVD (VobSub) decoding
# --------------------------------------------------------------------------------------------

def parse_dvd_extradata(extradata):
    """
    Parse the VobSub .idx style header carried in the stream extradata.

    :param extradata: bytes
    :return: Tuple of (size tuple or None, list of 16 (r, g, b) tuples or None)
    """
    size = None
    palette = None
    text = extradata.decode('latin-1', errors='ignore')
    for line in text.splitlines():
        key, _, value = line.partition(':')
        key = key.strip().lower()
        if key == 'size':
            try:
                w, h = value.strip().lower().split('x')
                size = (int(w), int(h))
            except ValueError:
                pass
        elif key == 'palette':
            try:
                entries = [int(c.strip(), 16) for c in value.split(',') if c.strip()]
            except ValueError:
                continue
            if len(entries) >= 16:
                palette = [((c >> 16) & 0xff, (c >> 8) & 0xff, c & 0xff) for c in entries[:16]]
    return size, palette


def _decode_dvd_field(data, offset, width, row_count):
    """
    Decode one interlaced field of DVD RLE data.

    :return: List of rows, each a list of (value, run_length) with value 0-3
    """
    rows = []
    nibble = offset * 2
    max_nibble = len(data) * 2

    def next_nibble():
        nonlocal nibble
        if nibble >= max_nibble:
            raise BitmapSubtitleError("RLE data overrun")
        byte = data[nibble >> 1]
        value = (byte >> 4) if (nibble & 1) == 0 else (byte & 0x0f)
        nibble += 1
        return value

    for _ in range(row_count):
        runs = []
        x = 0
        while x < width:
            code = next_nibble()
            if code < 0x4:
                code = (code << 4) | next_nibble()
                if code < 0x10:
                    code = (code << 4) | next_nibble()
                    if code < 0x40:
                        code = (code << 4) | next_nibble()
            length = code >> 2
            if length == 0 or length > width - x:
                # A zero length fills to the end of the line
                length = width - x
            runs.append((code & 0x3, length))
            x += length
        rows.append(runs)
        # Each line starts on a byte boundary
        if nibble & 1:
            nibble += 1
    return rows


def decode_dvd_packet(data):
    """
    Decode a single DVD subpicture unit.

    :param data: Raw SPU bytes
    :return: dict describing the subpicture, or None if it holds no image
    """
    if len(data) < 4:
        return None

    ctrl_offset = struct.unpack('>H', data[2:4])[0]
    start = None
    stop = None
    forced = False
    colors = None
    alphas = None
    area = None
    field_offsets = None

    pos = ctrl_offset
    seen = set()
    while pos not in seen and pos + 4 <= len(data):
        seen.add(pos)
        date, next_pos = struct.unpack('>HH', data[pos:pos + 4])
        time_ms = date * 1024 / 90.0
        p = pos + 4
        while p < len(data):
            cmd = data[p]
            p += 1
            if cmd == 0x00:
                forced = True
                if start is None:
                    start = time_ms
            elif cmd == 0x01:
                if start is None:
                    start = time_ms
            elif cmd == 0x02:
                stop = time_ms
            elif cmd == 0x03:
                b0, b1 = data[p], data[p + 1]
                colors = [b1 & 0x0f, b1 >> 4, b0 & 0x0f, b0 >> 4]
                p += 2
            elif cmd == 0x04:
                b0, b1 = data[p], data[p + 1]
                alphas = [b1 & 0x0f, b1 >> 4, b0 & 0x0f, b0 >> 4]
                p += 2
            elif cmd == 0x05:
                d = data[p:p + 6]
                x1 = (d[0] << 4) | (d[1] >> 4)
                x2 = ((d[1] & 0x0f) << 8) | d[2]
                y1 = (d[3] << 4) | (d[4] >> 4)
                y2 = ((d[4] & 0x0f) << 8) | d[5]
                area = (x1, y1, x2, y2)
                p += 6
            elif cmd == 0x06:
                field_offsets = struct.unpack('>HH', data[p:p + 4])
                p += 4
            elif cmd == 0x07:
                # CHG_COLCON - the size includes its own two bytes
                p += struct.unpack('>H', data[p:p + 2])[0]
            else:
                # 0xff (end of sequence) or an unknown command
                break
        pos = next_pos

    if area is None or field_offsets is None:
        return None

    x1, y1, x2, y2 = area
    width = x2 - x1 + 1
    height = y2 - y1 + 1
    if width <= 0 or height <= 0:
        return None

    top = _decode_dvd_field(data, field_offsets[0], width, (height + 1) // 2)
    bottom = _decode_dvd_field(data, field_offsets[1], width, height // 2)
    rows = []
    for i in range(height):
        rows.append(top[i // 2] if i % 2 == 0 else bottom[i // 2])

    return {
        'start': start or 0,
        'stop': stop,
        'forced': forced,
        'x': x1,
        'y': y1,
        'width': width,
        'height': height,
        'colors': colors or [0, 1, 2, 3],
        'alphas': alphas if alphas is not None else [0, 15, 15, 15],
        'rows': rows,
    }


def _dvd_text_value(sub, palette):
    """
    Pick which of the four DVD pixel values holds the text fill.

    With a palette, the brightest visible colour is used. Without one, the value
    that least often borders transparent pixels is used: outlines and anti-aliasing
    sit against the background, the fill sits inside them. (Authoring tools do not
    agree on which DVD colour slot holds the fill, so the slot order is no help.)
    """
    used = set()
    for runs in sub['rows']:
        for value, _ in runs:
            used.add(value)
    visible = [v for v in range(4) if v in used and sub['alphas'][v] > 0]
    if not visible:
        return None
    if palette:
        def luminance(v):
            r, g, b = palette[sub['colors'][v]]
            return 0.299 * r + 0.587 * g + 0.114 * b
        return max(visible, key=luminance)
    if len(visible) == 1:
        return visible[0]

    transparent = {v for v in range(4) if sub['alphas'][v] == 0}
    run_count = {v: 0 for v in visible}
    edge_count = {v: 0 for v in visible}
    for runs in sub['rows']:
        for i, (value, _) in enumerate(runs):
            if value not in run_count:
                continue
            run_count[value] += 1
            left = runs[i - 1][0] if i > 0 else None
            right = runs[i + 1][0] if i + 1 < len(runs) else None
            if left is None or right is None or left in transparent or right in transparent:
                edge_count[value] += 1
    return min(visible, key=lambda v: edge_count[v] / run_count[v])


def dvd_events(file_in, stream, work_dir, timeout=600):
    """
    Decode a DVD subtitle stream into two-colour events.

    :param file_in: Path to the media file
    :param stream: Stream info dict ('index', 'subtitle_index', 'codec_name')
    :param work_dir: Directory for temporary files (unused)
    :param timeout: Seconds allowed for ffprobe
    :return: List of events
    """
    extradata, packets = read_stream_packets(file_in, stream['index'], timeout=timeout)
    _, palette = parse_dvd_extradata(extradata)
    events = []
    for pkt in packets:
        try:
            sub = decode_dvd_packet(pkt['data'])
        except (BitmapSubtitleError, IndexError, struct.error):
            continue
        if sub is None:
            continue
        text_value = _dvd_text_value(sub, palette)
        if text_value is None:
            continue
        start = pkt['pts'] + sub['start']
        end = None
        if sub['stop'] is not None and sub['stop'] > sub['start']:
            end = pkt['pts'] + sub['stop']
        elif pkt['duration'] > 0:
            end = pkt['pts'] + pkt['duration']
        rows = [_merge_runs([(1 if value == text_value else 0, length) for value, length in runs])
                for runs in sub['rows']]
        events.append({
            'start': start,
            'end': end,
            'images': [{
                'x': sub['x'],
                'y': sub['y'],
                'width': sub['width'],
                'height': sub['height'],
                'rows': rows,
            }],
        })
    return events


# --------------------------------------------------------------------------------------------
# PGS (Blu-ray) decoding
# --------------------------------------------------------------------------------------------

def read_sup_segments(sup_path):
    """
    Read the segments of a Blu-ray .sup file.

    :return: List of (pts_ms, segment_type, payload)
    """
    segments = []
    with open(sup_path, 'rb') as f:
        data = f.read()
    pos = 0
    while pos + 13 <= len(data):
        if data[pos:pos + 2] != b'PG':
            # Resync on the next segment header
            next_pos = data.find(b'PG', pos + 1)
            if next_pos < 0:
                break
            pos = next_pos
            continue
        pts, _, seg_type, size = struct.unpack('>IIBH', data[pos + 2:pos + 13])
        payload = data[pos + 13:pos + 13 + size]
        segments.append((pts / 90.0, seg_type, payload))
        pos += 13 + size
    return segments


def _decode_pgs_object(obj):
    """
    Decode PGS RLE data.

    :return: List of rows, each a list of (palette_index, run_length)
    """
    data = obj['data']
    width = obj['width']
    height = obj['height']
    rows = []
    runs = []
    i = 0
    n = len(data)
    while i < n and len(rows) < height:
        b = data[i]
        i += 1
        if b:
            runs.append((b, 1))
            continue
        if i >= n:
            break
        b = data[i]
        i += 1
        if b == 0:
            rows.append(runs)
            runs = []
            continue
        length = b & 0x3f
        if b & 0x40:
            length = (length << 8) | data[i]
            i += 1
        color = 0
        if b & 0x80:
            color = data[i]
            i += 1
        runs.append((color, length))
    while len(rows) < height:
        rows.append([(0, width)])
    return rows


def _binarize_pgs_rows(rows, palette):
    """
    Map PGS palette indexes to text (1) or background (0).

    Opaque colours brighter than the midpoint between the darkest and brightest
    opaque colours in use are text; outlines and shadows are darker. When all
    opaque colours are about the same brightness they are all text.

    :param rows: Rows of (palette_index, run_length)
    :param palette: dict of palette_index -> (Y, alpha)
    """
    used = {value for runs in rows for value, _ in runs}
    opaque = {v: palette[v][0] for v in used if v in palette and palette[v][1] >= 128}
    if not opaque:
        return None
    low = min(opaque.values())
    high = max(opaque.values())
    if high - low < 48:
        text = set(opaque)
    else:
        threshold = (low + high) / 2
        text = {v for v, y in opaque.items() if y >= threshold}
    return [_merge_runs([(1 if value in text else 0, length) for value, length in runs]) for runs in rows]


def pgs_events(file_in, stream, work_dir, timeout=300):
    """
    Decode a PGS subtitle stream into two-colour events.

    :param file_in: Path to the media file
    :param stream: Stream info dict ('index', 'subtitle_index', 'codec_name')
    :param work_dir: Directory for the temporary .sup file
    :param timeout: Seconds allowed for ffmpeg
    :return: List of events
    """
    sup_path = os.path.join(work_dir, f"stream_{stream['index']}.sup")
    cmd = [
        'ffmpeg',
        '-y',
        '-i', file_in,
        '-map', f"0:s:{stream['subtitle_index']}",
        '-c:s', 'copy',
        sup_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise BitmapSubtitleError(f"ffmpeg failed: {result.stderr.strip()[-500:]}")

    palettes = {}
    objects = {}
    pending = {}
    pcs = None
    current = None
    events = []

    for pts, seg_type, p in read_sup_segments(sup_path):
        try:
            if seg_type == 0x16:
                # Presentation composition segment
                width, height, _, _, state, _, palette_id, count = struct.unpack('>HHBHBBBB', p[:11])
                comps = []
                off = 11
                for _ in range(count):
                    obj_id, _, crop_flag, x, y = struct.unpack('>HBBHH', p[off:off + 8])
                    off += 8
                    if crop_flag & 0x80:
                        off += 8
                    comps.append((obj_id, x, y))
                if state & 0x80:
                    # Epoch start - earlier objects and palettes are discarded
                    objects.clear()
                    palettes.clear()
                    pending.clear()
                pcs = {'pts': pts, 'palette_id': palette_id, 'comps': comps}
            elif seg_type == 0x14:
                # Palette definition segment
                palette = palettes.setdefault(p[0], {})
                for off in range(2, len(p) - 4, 5):
                    index, y, _, _, alpha = p[off:off + 5]
                    palette[index] = (y, alpha)
            elif seg_type == 0x15:
                # Object definition segment
                obj_id, _, flag = struct.unpack('>HBB', p[:4])
                if flag & 0x80:
                    width, height = struct.unpack('>HH', p[7:11])
                    pending[obj_id] = {'width': width, 'height': height, 'data': bytearray(p[11:])}
                elif obj_id in pending:
                    pending[obj_id]['data'] += p[4:]
                if flag & 0x40 and obj_id in pending:
                    objects[obj_id] = pending.pop(obj_id)
            elif seg_type == 0x80 and pcs is not None:
                # End of display set - whatever was shown ends here
                if current is not None:
                    current['end'] = pcs['pts']
                    events.append(current)
                    current = None
                palette = palettes.get(pcs['palette_id'], {})
                images = []
                for obj_id, x, y in pcs['comps']:
                    obj = objects.get(obj_id)
                    if obj is None:
                        continue
                    rows = _binarize_pgs_rows(_decode_pgs_object(obj), palette)
                    if rows and _has_text(rows):
                        images.append({'x': x, 'y': y, 'width': obj['width'], 'height': obj['height'], 'rows': rows})
                if images:
                    current = {
                        'start': pcs['pts'],
                        'end': None,
                        'images': images,
                    }
                pcs = None
        except (IndexError, struct.error, ValueError):
            continue

    if current is not None:
        events.append(current)
    return events


DECODERS = {
    'hdmv_pgs_subtitle': pgs_events,
    'pgssub': pgs_events,
    'dvd_subtitle': dvd_events,
    'dvdsub': dvd_events,
}


def is_supported(codec_name):
    return codec_name in DECODERS


def stream_events(file_in, stream, work_dir):
    """
    Decode one bitmap subtitle stream into two-colour events.

    :param file_in: Path to the media file
    :param stream: Stream info dict ('index', 'subtitle_index', 'codec_name')
    :param work_dir: Directory for temporary files
    :return: List of events
    """
    decoder = DECODERS.get(stream['codec_name'])
    if decoder is None:
        raise BitmapSubtitleError(f"Unsupported bitmap subtitle codec '{stream['codec_name']}'")
    return decoder(file_in, stream, work_dir)
