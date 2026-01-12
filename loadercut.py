#!/usr/bin/env python3
import sys


def remove_binary_section(filename, end_addr_hex):
    """
    バイナリファイルの0x20から指定番地-1までを削除する

    Args:
        filename: 対象のバイナリファイル
        end_addr_hex: 削除終点+1の番地（16進数文字列）
    """
    # 16進数を整数に変換
    end_addr = int(end_addr_hex, 16)

    # 削除範囲
    delete_start = 0x20
    delete_end = end_addr

    # バイナリファイルを読み込む
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print(f"エラー: ファイル '{filename}' が見つかりません")
        sys.exit(1)

    # ファイルサイズチェック
    if len(data) < delete_end:
        print(f"警告: ファイルサイズ({len(data)}バイト)が削除終点(0x{delete_end:04X})より小さいです")

    # 保持する部分を連結
    # [0x00-0x1F] + [end_addr以降]
    new_data = data[:delete_start] + data[delete_end:]

    # 元のファイルに上書き
    with open(filename, 'wb') as f:
        f.write(new_data)

    # 結果を表示
    deleted_bytes = len(data) - len(new_data)
    print(
        f"削除完了: 0x{delete_start:04X} - 0x{delete_end-1:04X} ({deleted_bytes}バイト)")
    print(f"元のサイズ: {len(data)} (0x{len(data):04X}) バイト")
    print(f"新サイズ: {len(new_data)} (0x{len(new_data):04X}) バイト")


def main():
    if len(sys.argv) != 3:
        print("使用法: python remove_section.py <バイナリファイル> <終点+1の番地(16進)>")
        print("例: python remove_section.py loader.bin 3000")
        print("    → 0x0020-0x2FFFを削除")
        sys.exit(1)

    filename = sys.argv[1]
    end_addr_hex = sys.argv[2]

    # "0x"プレフィックスがあれば削除
    if end_addr_hex.lower().startswith('0x'):
        end_addr_hex = end_addr_hex[2:]
    # "h"サフィックスがあれば削除
    if end_addr_hex.lower().endswith('h'):
        end_addr_hex = end_addr_hex[:-1]

    remove_binary_section(filename, end_addr_hex)


if __name__ == "__main__":
    main()
