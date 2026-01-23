#!/usr/bin/env python3
# change_sossys_d88.py - SORD M23 SOS d88ディスクイメージのSOS.SYS置換ツール

import sys
import os
import struct

# ディスク構成定数
SECTOR_SIZE = 256
SECTORS_PER_TRACK = 16
TRACK_SIZE = SECTOR_SIZE * SECTORS_PER_TRACK

# SOS.SYSの格納位置は、第2トラック第1セクタから、第4トラック第16セクタに収まるサイズであるべき。
# SOS.SYSのサイズは、引数で与えられたファイルのサイズに依存
SOS_SYS_Track_Start = 2
SOS_SYS_Track_End = 4
SOS_SYS_Sector_Start = 1

MAX_SOS_SYS_SIZE = (SOS_SYS_Track_End - SOS_SYS_Track_Start + 1) * SECTORS_PER_TRACK * SECTOR_SIZE  # 

# d88ヘッダーサイズ
D88_HEADER_SIZE = 0x2B0  # 688バイト
D88_SECTOR_HEADER_SIZE = 16


class D88Image:
    def __init__(self, filename):
        self.filename = filename
        with open(filename, 'rb') as f:
            self.data = bytearray(f.read())
        
        # ヘッダー解析
        self.disk_name = self.data[0:17].split(b'\x00')[0].decode('shift-jis', errors='ignore')
        self.protect = self.data[0x1A]
        self.disk_type = self.data[0x1B]
        self.disk_size = struct.unpack('<I', self.data[0x1C:0x20])[0]
        
        # トラックテーブル（164エントリ、各4バイト）
        self.track_table = []
        for i in range(164):
            offset = struct.unpack('<I', self.data[0x20 + i*4:0x20 + i*4 + 4])[0]
            self.track_table.append(offset)
        
        print(f"D88イメージ読み込み: {filename}")
        print(f"  ディスク名: {self.disk_name}")
        print(f"  ディスクサイズ: {self.disk_size} バイト")
    
    def extract_raw_image(self):
        """d88からrawイメージを抽出"""
        raw_image = bytearray()
        
        for track_num in range(164):
            track_offset = self.track_table[track_num]
            if track_offset == 0:
                # このトラックは存在しない
                break
            
            # 次のトラックの開始位置を探す（終了位置の判定用）
            next_track_offset = self.disk_size
            for i in range(track_num + 1, 164):
                if self.track_table[i] != 0:
                    next_track_offset = self.track_table[i]
                    break
            
            # このトラックのセクタを読む
            sectors = {}  # セクタ番号 -> セクタデータ
            pos = track_offset
            
            while pos < next_track_offset:
                if pos + D88_SECTOR_HEADER_SIZE > len(self.data):
                    break
                
                # セクタヘッダー解析
                c = self.data[pos]      # トラック番号
                h = self.data[pos + 1]  # ヘッド番号
                r = self.data[pos + 2]  # セクタ番号
                n = self.data[pos + 3]  # セクタサイズコード
                
                # セクタサイズを計算 (N: 0=128, 1=256, 2=512, 3=1024)
                sector_size = 128 << n
                
                # セクタデータを抽出
                sector_data = self.data[pos + D88_SECTOR_HEADER_SIZE:pos + D88_SECTOR_HEADER_SIZE + sector_size]
                sectors[r] = sector_data
                
                pos += D88_SECTOR_HEADER_SIZE + sector_size
            
            # セクタ番号順にrawイメージに追加
            for sector_num in range(1, SECTORS_PER_TRACK + 1):
                if sector_num in sectors:
                    raw_image.extend(sectors[sector_num])
                else:
                    # セクタが存在しない場合は0x00で埋める
                    raw_image.extend(b'\x00' * SECTOR_SIZE)
        
        return raw_image
    
    def update_from_raw_image(self, raw_image):
        """rawイメージの内容でd88イメージを更新"""
        raw_pos = 0
        
        for track_num in range(164):
            track_offset = self.track_table[track_num]
            if track_offset == 0:
                break
            
            # 次のトラックの開始位置
            next_track_offset = self.disk_size
            for i in range(track_num + 1, 164):
                if self.track_table[i] != 0:
                    next_track_offset = self.track_table[i]
                    break
            
            # このトラックのセクタを更新
            pos = track_offset
            
            while pos < next_track_offset:
                if pos + D88_SECTOR_HEADER_SIZE > len(self.data):
                    break
                
                # セクタヘッダー解析
                r = self.data[pos + 2]  # セクタ番号
                n = self.data[pos + 3]  # セクタサイズコード
                sector_size = 128 << n
                
                # rawイメージから対応するセクタデータを取得
                # rawイメージ内の位置 = トラック番号 * TRACK_SIZE + (セクタ番号 - 1) * SECTOR_SIZE
                raw_sector_pos = track_num * TRACK_SIZE + (r - 1) * SECTOR_SIZE
                
                if raw_sector_pos + sector_size <= len(raw_image):
                    # セクタデータを更新
                    self.data[pos + D88_SECTOR_HEADER_SIZE:pos + D88_SECTOR_HEADER_SIZE + sector_size] = \
                        raw_image[raw_sector_pos:raw_sector_pos + sector_size]
                
                pos += D88_SECTOR_HEADER_SIZE + sector_size
    
    def save(self, filename):
        """d88イメージをファイルに保存"""
        with open(filename, 'wb') as f:
            f.write(self.data)
        print(f"D88イメージ保存: {filename}")


# SOS.SYSの配置は、第2トラック、第1セクタから、第4トラック第16セクタに固定されている




def main():
    # コマンドライン引数の解析
    if len(sys.argv) < 3:
        print("使用方法: python change_sossys_d88.py <d88.d88> <新SOS.SYS> [<d88_new.d88>]")
        sys.exit(1)
    
    d88_file = sys.argv[1]
    sossys_file = sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) > 3 else d88_file
    
    # 入力ファイルの存在確認
    if not os.path.exists(d88_file):
        print(f"エラー: d88イメージ '{d88_file}' が見つかりません")
        sys.exit(1)
    
    if not os.path.exists(sossys_file):
        print(f"エラー: SOS.SYSファイル '{sossys_file}' が見つかりません")
        sys.exit(1)
    
    # 新しいSOS.SYSを読み込む
    with open(sossys_file, 'rb') as f:
        new_sossys = f.read()
    
    # サイズチェック
    if len(new_sossys) > MAX_SOS_SYS_SIZE:
        print(f"エラー: SOS.SYSのサイズが大きすぎます ({len(new_sossys)} > {MAX_SOS_SYS_SIZE})")
        sys.exit(1)
    
    # 8192バイトに満たない場合は0x00でパディング
    if len(new_sossys) < MAX_SOS_SYS_SIZE:
        new_sossys += b'\x00' * (MAX_SOS_SYS_SIZE - len(new_sossys))
    
    print(f"新SOS.SYSサイズ: {len(new_sossys)} バイト")
    
    # d88イメージを読み込む
    d88 = D88Image(d88_file)
    
    # rawイメージを抽出
    print("\nrawイメージを抽出中...")
    raw_image = d88.extract_raw_image()
    print(f"rawイメージサイズ: {len(raw_image)} バイト")
    
    # SOS.SYSを置き換え
    print("\nSOS.SYSを置き換え中...")
    # groupは使わずSOS.SYSを第2トラック第1セクタから書き込む
    sossys_pos = (SOS_SYS_Track_Start * TRACK_SIZE) + ((SOS_SYS_Sector_Start - 1) * SECTOR_SIZE)
    raw_image[sossys_pos:sossys_pos + len(new_sossys)] = new_sossys


    
    # d88イメージを更新
    print("\nd88イメージを更新中...")
    d88.update_from_raw_image(raw_image)
    
    # d88イメージを保存
    d88.save(output_file)
    
    print(f"\nSOS.SYSの置換が完了しました: {output_file}")


if __name__ == "__main__":
    main()