import os
import zlib
import ffmpy
import shutil
from queue import PriorityQueue

from PIL import Image

TMP_DIR = 'tmp'
width, height, interlace, skip, locality = 86, 64, 2, 3, 1

def create_workspace():
    if os.path.exists(TMP_DIR):
        shutil.rmtree(TMP_DIR)
    os.mkdir(TMP_DIR)

def check_size(data):
    count = [0 for i in range(257)]
    for i in data:
        count[i] += 1
    count[256] += 1
    q = PriorityQueue()
    for i in range(len(count)):
        q.put(count[i])
    size = 0
    while q.qsize() > 1:
        cur = q.get() + q.get()
        size += cur
        q.put(cur)
    return size // 8
# 256 : EOF, < 256 : char, > 256 : aux
def output_huffman(data, f):
    count = [0 for i in range(257)]
    node = 256
    for i in data:
        count[i] += 1
    count[256] += 1
    q = PriorityQueue()
    for i in range(len(count)):
        q.put((count[i], i))
    
    edges = [[0 for j in range(2)] for i in range(513)]
    rt = 0
    while q.qsize() > 1:
        first = q.get()
        second = q.get()
        node += 1
        cur = node
        rt = cur
        edges[cur][0] = first[1]
        edges[cur][1] = second[1]
        q.put((first[0] + second[0], cur))

    bitrep = [list() for i in range(257)]
    currep = []
    def dfs (x):
        if x <= 256:
            bitrep[x] = list(currep)
            return
        currep.append(0)
        dfs(edges[x][0])
        currep[-1] = 1
        dfs(edges[x][1])
        currep.pop()

    dfs(rt)
    bitarr = []
    data.append(256) 
    for i in data:
        for j in bitrep[i]:
            bitarr.append(j)
    data.pop()
    print(f"\nbitarr size = {len(bitarr) // 8}, data size = {len(data)}, com ratio = {len(bitarr) / len(data) / 8}")

    f.write(f"short huff_rt = {rt};\n")
    f.write("short huff[][2] = {")
    for i in range(257, node + 1):
        f.write(f"{{{edges[i][0]}, {edges[i][1]}}}, ")
    f.write('};\n')
    f.write('uint8_t video[] = {\n')
    for i in range(0, len(bitarr), 8):
        byte = 0
        for j in range(min(8, len(bitarr) - i)):
            byte |= bitarr[i + j] << j
        f.write(f"{byte},")
    f.write('};\n')

target_size = 125 * 1024

def split_video(video_dir):  
    gif_dir = os.path.join(TMP_DIR, 'bad.gif')

    ffmpy.FFmpeg(
        inputs  = {video_dir : None},
        outputs = {gif_dir   : None}
    ).run()

    im = Image.open(gif_dir)
    image_id = 0
    screen = [[0 for _ in range(width)] for _ in range(height)]

    data = []
    with open('badapple.h', 'w') as f:
        max_data = 0
        min_data = 1000
        tot_data = 0
        while True or len(data) < target_size * 1.45 or check_size(data) < target_size - 4096:
            st = len(data)
            try:
                frame = im.tell()
                png_dir = os.path.join(TMP_DIR, f'bad.png')

                image_id += 1 
                im.save(png_dir)
                im.seek(frame + 1)
                
                if image_id % skip == 0:
                    img = compress_image(png_dir)
                    chs = []
                    for w in range(image_id // skip % interlace, width, interlace):
                        ch = 0
                        for h in range(0, height, 8):
                            for hc in range(8):
                                if img[h + hc][w] != screen[h + hc][w]:
                                    ch |= 1 << (h // 8)
                        assert (ch < 256)
                        chs.append(ch)

                    for ws in range(image_id // skip % interlace, width, interlace * locality * 8):
                        wsend = min(ws + interlace * locality * 8, width)
                        cw = 0

                        for w in range(ws, wsend, interlace):
                            if chs[w // interlace] != 0:
                                cw |= 1 << ((w - ws) // locality // interlace)

                        data.append(cw)

                        for w in range(ws, wsend, interlace):
                            if (cw & (1 << ((w - ws) // locality // interlace))) != 0:
                                data.append(chs[w // interlace])

                                for h in range(0, height, 8):
                                    if (chs[w // interlace] >> (h // 8)) & 1:
                                        ret = 0
                                        for hc in range(7, -1, -1):
                                            ret = ret * 2 + (img[h + hc][w])
                                            assert img[h + hc][w] < 2
                                        assert ret < 256

                                        data.append(ret)

                                for h in range(height):
                                    screen[h][w] = img[h][w]
                            else:
                                for h in range(height):
                                    assert screen[h][w] == img[h][w]
                frame_size = len(data) - st
                max_data = max(max_data, frame_size)
                min_data = min(min_data, frame_size)
                tot_data += frame_size
                print(f"{image_id:4d}\tsize={frame_size:4d}\t\tmax={max_data:4d}\tmin={min_data:4d}\tavg={tot_data/image_id:3f}", end='\r')
            except EOFError:
                break
        output_huffman(data, f)

def compress_image(png_dir):
    png = Image.open(png_dir).resize((width, height), Image.ANTIALIAS)

    img = [[0 for _ in range(width)] for _ in range(height)]
    for i in range(height):
        for j in range(width):
            pixel = png.getpixel((j, i))
            img[i][j] = 1 if pixel > 127 else 0

    return img

def transfer(video_dir):
    create_workspace()
    split_video(video_dir)

if __name__ == '__main__':
    transfer('video/badapple-24fps.mp4')