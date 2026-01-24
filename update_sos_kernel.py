#!/usr/bin/env python3
"""
update_sos_kernel.py - S-OS Sword kernel updater for SORD M23

Updates the S-OS kernel in a d88 disk image.
Kernel location: Track 2 Sector 1 to Track 4 Sector 16
Disk format: 256 bytes/sector, 16 sectors/track, 80 tracks, single-sided
"""

import sys
import struct
from typing import BinaryIO

# Disk geometry constants
BYTES_PER_SECTOR = 256
SECTORS_PER_TRACK = 16
KERNEL_START_TRACK = 2
KERNEL_START_SECTOR = 1
KERNEL_END_TRACK = 4
KERNEL_END_SECTOR = 16
MAX_KERNEL_SIZE = (KERNEL_END_TRACK - KERNEL_START_TRACK + 1) * \
    SECTORS_PER_TRACK * BYTES_PER_SECTOR  # 12288 bytes

# D88 format constants
D88_HEADER_SIZE = 0x2B0
SECTOR_HEADER_SIZE = 16


class D88Image:
    """D88 disk image handler"""

    def __init__(self, filename: str):
        self.filename = filename
        with open(filename, 'rb') as f:
            self.data = bytearray(f.read())
        self._parse_header()
        self._build_sector_map()

    def _parse_header(self):
        """Parse D88 header"""
        self.disk_name = self.data[0:17]
        self.write_protect = self.data[0x1A]
        self.disk_type = self.data[0x1B]
        self.disk_size = struct.unpack('<I', self.data[0x1C:0x20])[0]

        # Track table (offset to each track)
        self.track_table = []
        for i in range(164):
            offset = struct.unpack('<I', self.data[0x20 + i*4:0x24 + i*4])[0]
            self.track_table.append(offset)

    def _build_sector_map(self):
        """Build a map of all sectors in the image"""
        self.sectors = {}  # Key: (track, sector), Value: offset in image

        for track_num in range(164):
            track_offset = self.track_table[track_num]
            if track_offset == 0:
                continue

            pos = track_offset
            while pos < len(self.data):
                if pos + SECTOR_HEADER_SIZE > len(self.data):
                    break

                # Read sector header
                c = self.data[pos]      # Cylinder (track)
                h = self.data[pos + 1]  # Head
                r = self.data[pos + 2]  # Record (sector ID)
                # Sector size (0=128, 1=256, 2=512, 3=1024)
                n = self.data[pos + 3]

                num_sectors = struct.unpack(
                    '<H', self.data[pos + 4:pos + 6])[0]
                data_size = struct.unpack(
                    '<H', self.data[pos + 14:pos + 16])[0]

                # Store sector location
                data_offset = pos + SECTOR_HEADER_SIZE
                self.sectors[(c, h, r)] = data_offset

                # Move to next sector
                pos = data_offset + data_size

                # If this was the last sector in this track, break
                if num_sectors <= 1:
                    break

    def write_sector_data(self, track: int, head: int, sector: int, data: bytes):
        """Write data to a specific sector"""
        key = (track, head, sector)
        if key not in self.sectors:
            raise ValueError(
                f"Sector not found: Track {track}, Head {head}, Sector {sector}")

        offset = self.sectors[key]
        if len(data) > BYTES_PER_SECTOR:
            raise ValueError(
                f"Data too large for sector: {len(data)} bytes (max {BYTES_PER_SECTOR})")

        # Pad data to sector size if needed
        padded_data = data + b'\x00' * (BYTES_PER_SECTOR - len(data))
        self.data[offset:offset + BYTES_PER_SECTOR] = padded_data

    def save(self, filename: str):
        """Save the modified image to a file"""
        with open(filename, 'wb') as f:
            f.write(self.data)


def update_kernel(kernel_file: str, input_d88: str, output_d88: str):
    """Update S-OS kernel in d88 disk image"""

    # Read kernel binary
    print(f"Reading kernel from: {kernel_file}")
    try:
        with open(kernel_file, 'rb') as f:
            kernel_data = f.read()
    except FileNotFoundError:
        print(f"Error: Kernel file not found: {kernel_file}", file=sys.stderr)
        return 1

    # Check kernel size
    kernel_size = len(kernel_data)
    print(f"Kernel size: {kernel_size} bytes")

    if kernel_size > MAX_KERNEL_SIZE:
        print(f"Error: Kernel too large! Size: {kernel_size} bytes, Maximum: {MAX_KERNEL_SIZE} bytes",
              file=sys.stderr)
        return 1

    # Load d88 image
    print(f"Loading d88 image: {input_d88}")
    try:
        image = D88Image(input_d88)
    except FileNotFoundError:
        print(f"Error: D88 image not found: {input_d88}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: Failed to parse d88 image: {e}", file=sys.stderr)
        return 1

    # Write kernel data to sectors
    print(
        f"Writing kernel to Track {KERNEL_START_TRACK}-{KERNEL_END_TRACK}, Sectors {KERNEL_START_SECTOR}-{KERNEL_END_SECTOR}")

    data_pos = 0
    head = 0  # Always head 0 (single-sided)

    for track in range(KERNEL_START_TRACK, KERNEL_END_TRACK + 1):
        start_sector = KERNEL_START_SECTOR if track == KERNEL_START_TRACK else 1
        end_sector = KERNEL_END_SECTOR if track == KERNEL_END_TRACK else SECTORS_PER_TRACK

        for sector in range(start_sector, end_sector + 1):
            if data_pos >= kernel_size:
                # Remaining sectors are filled with zeros
                sector_data = b'\x00' * BYTES_PER_SECTOR
            else:
                # Extract sector data from kernel
                remaining = kernel_size - data_pos
                chunk_size = min(BYTES_PER_SECTOR, remaining)
                sector_data = kernel_data[data_pos:data_pos + chunk_size]
                data_pos += chunk_size

            try:
                image.write_sector_data(track, head, sector, sector_data)
                print(
                    f"  Written: Track {track}, Sector {sector} ({len(sector_data)} bytes)")
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1

    # Save modified image
    print(f"Saving modified image to: {output_d88}")
    try:
        image.save(output_d88)
    except Exception as e:
        print(f"Error: Failed to save image: {e}", file=sys.stderr)
        return 1

    print("Success! Kernel updated successfully.")
    return 0


def main():
    """Main entry point"""
    if len(sys.argv) < 3:
        print(
            "Usage: update_sos_kernel.py <kernel_binary> <input_d88> [output_d88]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Arguments:", file=sys.stderr)
        print("  kernel_binary  : New S-OS kernel binary file (e.g., sos.sys)", file=sys.stderr)
        print("  input_d88      : Existing d88 disk image file", file=sys.stderr)
        print("  output_d88     : Output d88 disk image file (optional, defaults to input_d88)", file=sys.stderr)
        print("", file=sys.stderr)
        print("Kernel will be written to Track 2 Sector 1 through Track 4 Sector 16", file=sys.stderr)
        print(f"Maximum kernel size: {MAX_KERNEL_SIZE} bytes", file=sys.stderr)
        return 1

    kernel_file = sys.argv[1]
    input_d88 = sys.argv[2]
    output_d88 = sys.argv[3] if len(sys.argv) > 3 else input_d88

    if output_d88 == input_d88:
        print(f"Warning: Will overwrite the input file: {input_d88}")
        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return 0

    return update_kernel(kernel_file, input_d88, output_d88)


if __name__ == '__main__':
    sys.exit(main())
