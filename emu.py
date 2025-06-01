from machine import Pin, I2C
import random
import ssd1306
import time

# made by las-r on github
# v1.1
# based on chip-8-python v1.5

# usage:
# set `rom` variable to the name of
# the rom file in your flash memory

rom = "file name here"

# behavior settings
LEGACYSHIFT = False
LEGACYOFFSJUMP = False
LEGACYSTORE = False
DEBUG = False
HZ = 500

# display settings
ON = 1
OFF = 0
disp = [[False] * 64 for _ in range(32)]
dispDirty = False

# oled display
oled = ssd1306.SSD1306_I2C(128, 64, I2C(0, scl=Pin(22), sda=Pin(21)))

# keyboard
krows = [Pin(pinnum, Pin.OUT) for pinnum in (15, 2, 4, 13)]
kcols = [Pin(pinnum, Pin.IN, Pin.PULL_UP) for pinnum in (5, 18, 19, 14)]
keym = [
    [1, 2, 3, 12],
    [4, 5, 6, 13],
    [7, 8, 9, 14],
    [10, 0, 11, 15]
]
keys = [False] * 16

# cycle counter
cycles = 0

# buzzer
buzzer = Pin(33, Pin.OUT)
buzzing = False
buzzstart = 0

# memory
pc = 0x200
i = 0
ram = [0] * 4096
v = [0] * 16
stack = []

# timers
dtime = 0
stime = 0

# font
FONT = [[0xf0, 0x90, 0x90, 0x90, 0xf0],
        [0x20, 0x60, 0x20, 0x20, 0x70],
        [0xf0, 0x10, 0xf0, 0x80, 0xf0],
        [0xf0, 0x10, 0xf0, 0x10, 0xf0],
        [0x90, 0x90, 0xf0, 0x10, 0x10],
        [0xf0, 0x80, 0xf0, 0x10, 0xf0],
        [0xf0, 0x80, 0xf0, 0x90, 0xf0],
        [0xf0, 0x10, 0x20, 0x40, 0x40],
        [0xf0, 0x90, 0xf0, 0x90, 0xf0],
        [0xf0, 0x90, 0xf0, 0x10, 0xf0],
        [0xf0, 0x90, 0xf0, 0x90, 0x90],
        [0xe0, 0x90, 0xe0, 0x90, 0xe0],
        [0xf0, 0x80, 0x80, 0x80, 0xf0],
        [0xe0, 0x90, 0x90, 0x90, 0xe0],
        [0xf0, 0x80, 0xf0, 0x80, 0xf0],
        [0xf0, 0x80, 0xf0, 0x80, 0x80]]
for idx, char in enumerate(FONT):
        for j, byte in enumerate(char):
            ram[0x50 + idx * 5 + j] = byte

# scan keys
@micropython.native
def scanKeys():
    for rowidx, rowpin in enumerate(krows):
        rowpin.value(0)
        for colidx, colpin in enumerate(kcols):
            keyval = keym[rowidx][colidx]
            keys[keyval] = not colpin.value()
        rowpin.value(1)
            
# update screen
@micropython.native
def updScreen():
    oled.fill(OFF)
    for r, row in enumerate(disp):
        for c, pix in enumerate(row):
            if pix:
                oled.pixel(c * 2, r * 2, 1)
                oled.pixel(c * 2, r * 2 + 1, 1)
                oled.pixel(c * 2 + 1, r * 2, 1)
                oled.pixel(c * 2 + 1, r * 2 + 1, 1)
    oled.show()
    
# read rom function
@micropython.native
def loadRom(rom):
    global ram
    
    with open(rom, "rb") as f:
        romd = f.read()
        for i in range(len(romd)):
            ram[0x200 + i] = romd[i]

# execute instruction function
@micropython.native
def execInst(inst):
    global pc, v, i, disp, dtime, stime, keys, dispDirty

    n1 = (inst & 0xF000) >> 12
    n2 = (inst & 0x0F00) >> 8
    n3 = (inst & 0x00F0) >> 4
    n4 = inst & 0x000F

    # debug
    if DEBUG:
        print(f"PC: {pc}  Opcode: {hex(inst)}")

    # increment pc
    pc += 2

    # fetch and run instruction
    if n1 == 0:
        if n2 == 0:
            if n3 == 14:
                if n4 == 0:
                    # clear screen
                    disp = [[False] * 64 for _ in range(32)]

                elif n4 == 14:
                    # return from subroutine
                    pc = stack.pop()

    elif n1 == 1:
        # jump
        pc = n4 + n3 * 16 + n2 * 256

    elif n1 == 2:
        # jump to subroutine
        if len(stack) >= 16:
            print("Stack overflow!")
        else:
            stack.append(pc)
        pc = n4 + n3 * 16 + n2 * 256

    elif n1 == 3:
        # skip inst if equal
        if v[n2] == n4 + n3 * 16:
            pc += 2

    elif n1 == 4:
        # skip inst if not equal
        if v[n2] != n4 + n3 * 16:
            pc += 2

    elif n1 == 5:
        if n4 == 0:
            # skip inst if v equal
            if v[n2] == v[n3]:
                pc += 2

    elif n1 == 6:
        # set vx
        v[n2] = (n4 + n3 * 16) & 255

    elif n1 == 7:
        # add to vx
        v[n2] = (v[n2] + (n3 * 16 + n4)) & 255

    elif n1 == 8:
        if n4 == 0:
            # set
            v[n2] = v[n3]

        elif n4 == 1:
            # or
            v[n2] = (v[n2] | v[n3]) & 255

        elif n4 == 2:
            # and
            v[n2] = (v[n2] & v[n3]) & 255

        elif n4 == 3:
            # xor
            v[n2] = (v[n2] ^ v[n3]) & 255

        elif n4 == 4:
            # add
            result = v[n2] + v[n3]
            v[15] = 1 if result > 255 else 0
            v[n2] = result & 255

        elif n4 == 5:
            # sub (vx - vy)
            v[15] = 1 if v[n2] > v[n3] else 0
            v[n2] = (v[n2] - v[n3]) & 255

        elif n4 == 6:
            # right shift
            if LEGACYSHIFT:
                v[n2] = v[n3]
            v[15] = v[n2] & 1
            v[n2] = (v[n2] >> 1) & 255

        elif n4 == 7:
            # sub (vy - vx)
            v[15] = 1 if v[n3] > v[n2] else 0
            v[n2] = (v[n3] - v[n2]) & 255

        elif n4 == 14:
            # left shift
            if LEGACYSHIFT:
                v[n2] = v[n3]
            v[15] = (v[n2] >> 7) & 1
            v[n2] = (v[n2] << 1) & 255

    elif n1 == 9:
        if n4 == 0:
            # skip inst if v not equal
            if v[n2] != v[n3]:
                pc += 2

    elif n1 == 10:
        # set i
        i = n4 + n3 * 16 + n2 * 256

    elif n1 == 11:
        # offset jump
        if LEGACYOFFSJUMP:
            pc = n4 + n3 * 16 + n2 * 256 + v[0]
        else:
            pc = n4 + n3 * 16 + v[n2]

    elif n1 == 12:
        v[n2] = random.randint(0, 255) & (n4 + n3 * 16)

    elif n1 == 13:
        # draw
        x = v[n2] % 64
        y = v[n3] % 32
        h = n4
        v[0xf] = 0
        for row in range(h):
            if i + row < len(ram):
                spr = ram[i + row]
            else:
                spr = 0
            for col in range(8):
                if (spr >> (7 - col)) & 1:
                    dx = (x + col) % 64
                    dy = (y + row) % 32
                    if disp[dy][dx]:
                        v[0xf] = 1
                    disp[dy][dx] ^= True
        dispDirty = True

    elif n1 == 14:
        if n3 == 9 and n4 == 14:
            # skip if key
            if keys[v[n2]]:
                pc += 2

        elif n3 == 10 and n4 == 1:
            # skip if not key
            if not keys[v[n2]]:
                pc += 2

    elif n1 == 15:
        if n3 == 0 and n4 == 7:
            # set vx to dt
            v[n2] = dtime

        elif n3 == 1:
            if n4 == 5:
                # set dt to vx
                dtime = v[n2]

            elif n4 == 8:
                # set st to vx
                stime = v[n2]

            elif n4 == 14:
                # i + vx
                i += v[n2]

        elif n3 == 2 and n4 == 9:
            # set i to font char
            i = 0x50 + v[n2] * 5

        elif n3 == 3 and n4 == 3:
            # decimal convert
            ram[i] = v[n2] // 100
            ram[i + 1] = (v[n2] % 100) // 10
            ram[i + 2] = v[n2] % 10

        elif n3 == 5 and n4 == 5:
            # store mem
            for ivx in range(n2 + 1):
                ram[i + ivx] = v[ivx]
                if LEGACYSTORE:
                    i += 1

        elif n3 == 6 and n4 == 5:
            # load mem
            for ilx in range(n2 + 1):
                v[ilx] = ram[i + ilx]
                                
# load rom
loadRom(rom)

# main loop
run = True
while run and pc < len(ram):
    # input
    scanKeys()
        
    # execute
    for _ in range(HZ // 60):
        execInst((ram[pc] << 8) | ram[pc + 1])
        cycles += 1
    
    # debug
    if DEBUG:
        print(f"Keys:")
        print(keys[:3])
        print(keys[4:7])
        print(keys[8:11])
        print(keys[12:15])
        print(f"Cycles: {cycles}")
            
    # delay timer
    if dtime > 0:
        dtime -= 1
        
    # sound timer
    if stime > 0:
        if not buzzing:
            buzzer.value(1)
            buzzing = True
            buzzstart = time.ticks_ms()
        stime -= 1
    elif buzzing:
        if time.ticks_diff(time.ticks_ms(), buzzstart) > 16:
            buzzer.value(0)
            buzzing = False
            
    # update screen
    if dispDirty:
        updScreen()
        dispDirty = False
    
    # refresh rate
    time.sleep(0.0167)
