#include <stdint.h>
#include <chrono>
using namespace std;

#include "badapple.h"
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

void oled_init();
void oled_clear();
void oled_write_byte(uint8_t, uint8_t, uint8_t);
void HAL_Delay(int);

uint8_t get_next_byte();
void reset_decoder();
uint8_t decode_EOF();

const int width = 86, height = 64, interlace = 2, skip = 3, locality = 1;

int main() {
	oled_init();

	int frame = 0;

	while (1)
	{
		frame = 0;
		reset_decoder();
		oled_clear();
		auto dtn = chrono::system_clock::now().time_since_epoch().count();
		while (!decode_EOF())
		{
			frame++;
			for (int wstart = frame % interlace; wstart < width; wstart += 8 * interlace * locality) {
				uint8_t wmask = get_next_byte();
				int wend = wstart + 8 * interlace * locality;
				if (wend > width)
					wend = width;
				for (int wrow = 0; wstart + wrow < wend; wrow += interlace) {
					if ((wmask >> (wrow / interlace / locality)) & 1) {
						int i = wstart + wrow;
						uint8_t mask = get_next_byte();
						for (int j = 0; j < 8; j++) {
							if ((mask >> j) & 1) {
								uint8_t chunk = get_next_byte();
								oled_write_byte(i, j, chunk);
							}
						}
					}
				}
			}
            while (chrono::system_clock::now().time_since_epoch().count() - dtn < 41666666ll * frame * skip) {
            	printf("\033[33;H%2.3lf", (chrono::system_clock::now().time_since_epoch().count() - dtn) / 1e9);
            	fflush(stdout);
            	usleep(1000);
			}
		}
	}
}

uint8_t oled[86][8];

void oled_init() {
    printf("\033[2J");
}

void oled_clear() {
	oled_init();
}

void oled_write_byte(uint8_t x, uint8_t y, uint8_t chunk) {
	oled[x][y] = chunk;
    y *= 4;
    for (int j = 0; j < 8; j += 2) {
        uint8_t d1 = (chunk >> j) & 1, d2 = (chunk >> (j + 1)) & 1;
        printf("\033[%d;%dH%s", y, x, d1 ? (d2 ? "\u2588" : "\u2580") : (d2 ? "\u2584" : " "));
        y++;
    }
}

int bitpos;
uint8_t next_byte, EOF_flag;

uint8_t next_bit() {
	uint8_t ret = (video[bitpos >> 3] >> (bitpos & 7)) & 1;
	bitpos ++;
	return ret;
}

void check_next_byte() {
	int x = huff_rt;
	while (x > 256) {
		x = huff[x - 257][next_bit()];
	}
	if (x == 256) EOF_flag = 1;
	else next_byte = x;
}

uint8_t get_next_byte() {
	uint8_t ret = next_byte;
	check_next_byte();
	return ret;
}
uint8_t decode_EOF() {
	return EOF_flag;
}


void reset_decoder() {
	bitpos = 0;
	EOF_flag = 0;
	check_next_byte();
}
