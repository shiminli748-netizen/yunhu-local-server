#!/usr/bin/env python3
"""
APK v2 签名脚本

为 Android APK 文件添加 APK Signature Scheme v2 签名。
使用纯 Python 实现，依赖 cryptography 和 pyjks 库。

APK v2 签名格式:
  [ZIP 内容][APK Signing Block][ZIP Central Directory][ZIP End of Central Directory]

APK Signing Block 格式:
  8 bytes: block size (小端, 不含此字段)
  ID-value pairs:
    8 bytes: pair size (小端, 不含此字段)
    4 bytes: ID (0x7109871a for v2)
    value data
  8 bytes: block size (小端, 同上)
  16 bytes: magic "APK Sig Block 42"
"""

import argparse
import hashlib
import os
import struct
import subprocess
import sys
import tempfile

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509 import load_der_x509_certificate


# ============================================================
# 常量定义
# ============================================================

APK_SIGNING_BLOCK_MAGIC = b'APK Sig Block 42'
APK_SIGNATURE_SCHEME_V2_BLOCK_ID = 0x7109871a

# 摘要算法 ID (APK Signature Scheme v2)
DIGEST_SHA256 = 0x0103

# 签名算法 ID
SIGNATURE_RSA_PKCS1_V1_5_WITH_SHA256 = 0x0101

# 分块大小 (1 MB)
CHUNK_SIZE = 1024 * 1024

# ZIP End of Central Directory 签名
EOCD_SIGNATURE = b'\x50\x4b\x05\x06'


# ============================================================
# Protobuf 编码
# ============================================================

def encode_varint(value):
    """将整数编码为 protobuf varint 格式。"""
    if value < 0:
        raise ValueError("Varint 不支持负数")
    result = bytearray()
    while value > 0x7f:
        result.append((value & 0x7f) | 0x80)
        value >>= 7
    result.append(value & 0x7f)
    return bytes(result)


def encode_field_varint(field_number, value):
    """编码 varint 类型字段 (wire type 0)。"""
    tag = (field_number << 3) | 0
    return encode_varint(tag) + encode_varint(value)


def encode_field_bytes(field_number, data):
    """编码长度限定字段 (wire type 2)，用于 bytes、嵌入消息等。"""
    tag = (field_number << 3) | 2
    return encode_varint(tag) + encode_varint(len(data)) + data


# ============================================================
# Protobuf 消息构建
# ============================================================

def encode_digest_proto(algorithm, digest_bytes):
    """
    编码 Digest 消息:
      message Digest {
          uint32 algorithm = 1;
          bytes digest = 2;
      }
    """
    msg = bytearray()
    msg += encode_field_varint(1, algorithm)
    msg += encode_field_bytes(2, digest_bytes)
    return bytes(msg)


def encode_signature_proto(algorithm, signature_bytes):
    """
    编码 Signature 消息:
      message Signature {
          uint32 algorithm = 1;
          bytes signature = 2;
      }
    """
    msg = bytearray()
    msg += encode_field_varint(1, algorithm)
    msg += encode_field_bytes(2, signature_bytes)
    return bytes(msg)


def encode_signed_data_proto(digest_protos, cert_ders):
    """
    编码 SignedData 消息:
      message SignedData {
          repeated Digest digests = 1;
          repeated bytes certificates = 2;
          repeated Attribute additional_attributes = 3;
      }
    """
    msg = bytearray()
    for dp in digest_protos:
        msg += encode_field_bytes(1, dp)
    for cd in cert_ders:
        msg += encode_field_bytes(2, cd)
    # additional_attributes 为空，不编码
    return bytes(msg)


def encode_signer_proto(signed_data_bytes, signature_protos, public_key_der):
    """
    编码 Signer 消息:
      message Signer {
          bytes signed_data = 1;
          repeated Signature signatures = 2;
          bytes public_key = 3;
      }
    """
    msg = bytearray()
    msg += encode_field_bytes(1, signed_data_bytes)
    for sp in signature_protos:
        msg += encode_field_bytes(2, sp)
    msg += encode_field_bytes(3, public_key_der)
    return bytes(msg)


def encode_v2_block_proto(signer_protos):
    """
    编码 APKSignatureSchemeV2Block 消息:
      message APKSignatureSchemeV2Block {
          repeated Signer signers = 1;
      }
    """
    msg = bytearray()
    for sp in signer_protos:
        msg += encode_field_bytes(1, sp)
    return bytes(msg)


# ============================================================
# APK Signing Block 构建
# ============================================================

def encode_id_value_pair(block_id, value):
    """
    编码 APK Signing Block 中的 ID-value 对。
    格式: 8 bytes pair size (不含此字段) + 4 bytes ID + value data
    """
    id_and_value = struct.pack('<I', block_id) + value
    pair_size = len(id_and_value)
    return struct.pack('<Q', pair_size) + id_and_value


def build_signing_block(v2_block_bytes):
    """
    构建 APK Signing Block。
    格式:
      8 bytes: block size (不含此字段，即 pairs + 第二个 size + magic)
      ID-value pairs
      8 bytes: block size (同上)
      16 bytes: magic "APK Sig Block 42"
    """
    pair_data = encode_id_value_pair(APK_SIGNATURE_SCHEME_V2_BLOCK_ID, v2_block_bytes)
    pairs_size = len(pair_data)
    # block_size = pairs_size + 8 (第二个 size) + 16 (magic)
    block_size = pairs_size + 24

    block = bytearray()
    block += struct.pack('<Q', block_size)   # 第一个 size
    block += pair_data                       # ID-value 对
    block += struct.pack('<Q', block_size)   # 第二个 size
    block += APK_SIGNING_BLOCK_MAGIC         # magic
    return bytes(block)


# ============================================================
# ZIP/APK 解析
# ============================================================

def find_eocd(data):
    """
    在 ZIP 数据中查找 End of Central Directory 记录。
    从文件末尾向前搜索，考虑最大 65535 字节的注释。
    """
    max_comment = 65535
    search_start = max(0, len(data) - max_comment - 22)

    for i in range(len(data) - 22, search_start - 1, -1):
        if data[i:i + 4] == EOCD_SIGNATURE:
            comment_len = struct.unpack('<H', data[i + 20:i + 22])[0]
            if i + 22 + comment_len == len(data):
                return i

    raise ValueError("无法找到 ZIP End of Central Directory 记录")


def parse_eocd(data, eocd_offset):
    """解析 EOCD，返回 Central Directory 偏移量、大小和注释长度。"""
    cd_size = struct.unpack('<I', data[eocd_offset + 12:eocd_offset + 16])[0]
    cd_offset = struct.unpack('<I', data[eocd_offset + 16:eocd_offset + 20])[0]
    comment_len = struct.unpack('<H', data[eocd_offset + 20:eocd_offset + 22])[0]
    return cd_offset, cd_size, comment_len


def update_eocd_cd_offset(eocd_data, new_cd_offset):
    """更新 EOCD 中的 Central Directory 偏移量。"""
    eocd = bytearray(eocd_data)
    struct.pack_into('<I', eocd, 16, new_cd_offset)
    return bytes(eocd)


def strip_existing_signing_block(data, cd_offset):
    """
    如果存在 APK Signing Block，将其剥离。
    返回 ZIP 条目数据的结束偏移量（即签名块之前的位置）。
    """
    if cd_offset < 32:
        return cd_offset

    # 检查 magic（位于 CD 之前 16 字节）
    magic_offset = cd_offset - 16
    if data[magic_offset:magic_offset + 16] != APK_SIGNING_BLOCK_MAGIC:
        return cd_offset

    # 读取第二个 size 字段（位于 magic 之前 8 字节）
    block_size = struct.unpack('<Q', data[cd_offset - 24:cd_offset - 16])[0]

    # block_size = pairs_size + 24
    # 总块大小 = 8 (第一个 size) + block_size = block_size + 8
    # 块起始位置 = cd_offset - block_size - 8
    entries_end = cd_offset - block_size - 8

    # 验证第一个 size 字段
    first_size = struct.unpack('<Q', data[entries_end:entries_end + 8])[0]
    if first_size != block_size:
        raise ValueError("APK Signing Block 的 size 字段不匹配")

    return entries_end


# ============================================================
# 摘要计算
# ============================================================

def compute_chunk_digests(data):
    """
    计算数据的分块摘要（用于 APK v2 签名）。
    将数据按 1MB 分块，每块计算 SHA-256，
    然后拼接: chunk_count (uint32 LE) + 各块摘要，
    最后对拼接结果计算 SHA-256。
    """
    if len(data) == 0:
        chunks = [b'']
    else:
        chunks = [data[i:i + CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE)]

    chunk_digests = b''.join(hashlib.sha256(chunk).digest() for chunk in chunks)
    content_digest_input = struct.pack('<I', len(chunks)) + chunk_digests
    return hashlib.sha256(content_digest_input).digest()


def compute_apk_digest(entries_data, cd_data, eocd_data):
    """
    计算 APK v2 摘要。
    对三个部分分别计算分块摘要，然后拼接:
      0xa5 + len(entries) as uint64 LE + entries_digest
            + len(cd) as uint64 LE + cd_digest
            + len(eocd) as uint64 LE + eocd_digest
    最后对拼接结果计算 SHA-256。
    """
    d1 = compute_chunk_digests(entries_data)
    d2 = compute_chunk_digests(cd_data)
    d3 = compute_chunk_digests(eocd_data)

    overall_input = (
        b'\xa5' +
        struct.pack('<Q', len(entries_data)) + d1 +
        struct.pack('<Q', len(cd_data)) + d2 +
        struct.pack('<Q', len(eocd_data)) + d3
    )
    return hashlib.sha256(overall_input).digest()


# ============================================================
# 密钥加载
# ============================================================

def load_key_from_jks(keystore_path, alias, storepass, keypass):
    """
    从 keystore 加载 RSA 私钥和证书链。
    支持 JKS 和 PKCS#12 两种格式。
    优先尝试 PKCS#12（cryptography 原生支持），失败后尝试 JKS（通过 pyjks 或 keytool 转换）。
    """
    with open(keystore_path, 'rb') as f:
        ks_data = f.read()

    # 1. 尝试作为 PKCS#12 加载
    try:
        return _load_from_pkcs12(ks_data, keypass)
    except Exception:
        pass

    # 2. 尝试使用 pyjks 加载 JKS
    try:
        return _load_from_jks_pyjks(ks_data, alias, storepass, keypass)
    except Exception:
        pass

    # 3. 尝试使用 keytool 将 JKS 转换为 PKCS#12 后加载
    try:
        return _load_from_jks_via_keytool(keystore_path, alias, storepass, keypass)
    except Exception:
        pass

    raise ValueError(
        f"无法加载 keystore '{keystore_path}'。"
        "请确保文件为有效的 JKS 或 PKCS#12 格式，且密码正确。"
    )


def _load_from_pkcs12(ks_data, keypass):
    """从 PKCS#12 格式的 keystore 数据加载密钥和证书。"""
    password = keypass.encode('utf-8') if keypass else None
    private_key, cert, chain = pkcs12.load_key_and_certificates(ks_data, password)
    if private_key is None:
        raise ValueError("PKCS#12 中未找到私钥")
    cert_chain = [cert] if cert else []
    if chain:
        cert_chain.extend(chain)
    return private_key, cert_chain


def _load_from_jks_pyjks(ks_data, alias, storepass, keypass):
    """使用 pyjks 库从 JKS 格式加载密钥和证书。"""
    import jks

    ks = jks.KeyStore.loads(ks_data, storepass, try_decrypt_keys=False)

    if alias not in ks.private_keys:
        raise ValueError(f"别名 '{alias}' 在 keystore 中未找到或不是私钥条目")

    pk_entry = ks.private_keys[alias]

    if not pk_entry.is_decrypted():
        pk_entry.decrypt(keypass)

    priv_key = serialization.load_der_private_key(pk_entry.pkey_pkcs8, password=None)

    cert_objects = []
    for cert_type, cert_der in pk_entry.cert_chain:
        cert_obj = load_der_x509_certificate(cert_der)
        cert_objects.append(cert_obj)

    return priv_key, cert_objects


def _load_from_jks_via_keytool(keystore_path, alias, storepass, keypass):
    """使用 keytool 将 JKS 转换为 PKCS#12 后加载密钥和证书。"""
    p12_path = tempfile.mktemp(suffix='.p12')

    try:
        cmd = [
            'keytool', '-importkeystore',
            '-srckeystore', keystore_path,
            '-srcstoretype', 'JKS',
            '-srcstorepass', storepass,
            '-srcalias', alias,
            '-srckeypass', keypass,
            '-destkeystore', p12_path,
            '-deststoretype', 'PKCS12',
            '-deststorepass', storepass,
            '-destkeypass', keypass,
            '-noprompt',
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"keytool 转换失败: {result.stdout} {result.stderr}")

        with open(p12_path, 'rb') as f:
            p12_data = f.read()

        return _load_from_pkcs12(p12_data, keypass)
    finally:
        if os.path.exists(p12_path):
            os.unlink(p12_path)


# ============================================================
# 主签名函数
# ============================================================

def sign_apk(input_path, keystore_path, alias, storepass, keypass, output_path):
    """为 APK 添加 v2 签名。"""

    # 1. 加载密钥和证书
    print("正在加载密钥...")
    private_key, cert_chain = load_key_from_jks(keystore_path, alias, storepass, keypass)

    # 获取证书 DER 编码
    cert_ders = [cert.public_bytes(serialization.Encoding.DER) for cert in cert_chain]

    # 获取公钥 DER 编码 (SubjectPublicKeyInfo 格式)
    public_key = private_key.public_key()
    public_key_der = public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # 2. 读取 APK 文件
    print("正在读取 APK...")
    with open(input_path, 'rb') as f:
        apk_data = f.read()

    # 3. 解析 ZIP 结构
    eocd_offset = find_eocd(apk_data)
    cd_offset, cd_size, comment_len = parse_eocd(apk_data, eocd_offset)

    print(f"  EOCD 偏移: {eocd_offset}")
    print(f"  CD 偏移: {cd_offset}, 大小: {cd_size}")

    # 4. 剥离已有的 APK Signing Block
    entries_end = strip_existing_signing_block(apk_data, cd_offset)
    if entries_end < cd_offset:
        print(f"  已剥离现有签名块 (原块大小: {cd_offset - entries_end} 字节)")

    # 5. 提取三个部分的数据
    entries_data = apk_data[:entries_end]
    cd_data = apk_data[cd_offset:eocd_offset]
    eocd_data = apk_data[eocd_offset:]

    # 6. 第一轮: 构建预备签名块以确定大小
    #    使用原始 EOCD 计算初步摘要
    preliminary_digest = compute_apk_digest(entries_data, cd_data, eocd_data)
    digest_proto = encode_digest_proto(DIGEST_SHA256, preliminary_digest)
    signed_data_proto = encode_signed_data_proto([digest_proto], cert_ders)

    # 签名 SignedData（不是原始摘要）
    preliminary_signature = private_key.sign(
        signed_data_proto, padding.PKCS1v15(), hashes.SHA256()
    )
    signature_proto = encode_signature_proto(
        SIGNATURE_RSA_PKCS1_V1_5_WITH_SHA256, preliminary_signature
    )
    signer_proto = encode_signer_proto(signed_data_proto, [signature_proto], public_key_der)
    v2_block_proto = encode_v2_block_proto([signer_proto])
    preliminary_signing_block = build_signing_block(v2_block_proto)

    # 7. 计算正确的 EOCD（更新 CD 偏移量）
    new_cd_offset = len(entries_data) + len(preliminary_signing_block)
    new_eocd_data = update_eocd_cd_offset(eocd_data, new_cd_offset)

    # 8. 第二轮: 使用正确的 EOCD 重新计算摘要和签名
    print("正在计算 v2 签名...")
    correct_digest = compute_apk_digest(entries_data, cd_data, new_eocd_data)

    digest_proto = encode_digest_proto(DIGEST_SHA256, correct_digest)
    signed_data_proto = encode_signed_data_proto([digest_proto], cert_ders)

    correct_signature = private_key.sign(
        signed_data_proto, padding.PKCS1v15(), hashes.SHA256()
    )
    signature_proto = encode_signature_proto(
        SIGNATURE_RSA_PKCS1_V1_5_WITH_SHA256, correct_signature
    )
    signer_proto = encode_signer_proto(signed_data_proto, [signature_proto], public_key_der)
    v2_block_proto = encode_v2_block_proto([signer_proto])
    signing_block = build_signing_block(v2_block_proto)

    # 验证签名块大小未变化（RSA 签名长度固定，所以应该一致）
    if len(signing_block) != len(preliminary_signing_block):
        print("警告: 签名块大小发生变化，需要迭代修正", file=sys.stderr)
        # 重新计算 EOCD 和签名
        new_cd_offset = len(entries_data) + len(signing_block)
        new_eocd_data = update_eocd_cd_offset(eocd_data, new_cd_offset)
        correct_digest = compute_apk_digest(entries_data, cd_data, new_eocd_data)
        digest_proto = encode_digest_proto(DIGEST_SHA256, correct_digest)
        signed_data_proto = encode_signed_data_proto([digest_proto], cert_ders)
        correct_signature = private_key.sign(
            signed_data_proto, padding.PKCS1v15(), hashes.SHA256()
        )
        signature_proto = encode_signature_proto(
            SIGNATURE_RSA_PKCS1_V1_5_WITH_SHA256, correct_signature
        )
        signer_proto = encode_signer_proto(signed_data_proto, [signature_proto], public_key_der)
        v2_block_proto = encode_v2_block_proto([signer_proto])
        signing_block = build_signing_block(v2_block_proto)

    # 9. 写入输出文件
    print("正在写入输出 APK...")
    with open(output_path, 'wb') as f:
        f.write(entries_data)
        f.write(signing_block)
        f.write(cd_data)
        f.write(new_eocd_data)

    output_size = os.path.getsize(output_path)
    input_size = os.path.getsize(input_path)
    print(f"\n签名完成!")
    print(f"  输入:   {input_path} ({input_size} 字节)")
    print(f"  输出:   {output_path} ({output_size} 字节)")
    print(f"  签名块: {len(signing_block)} 字节")
    print(f"  新 CD 偏移: {new_cd_offset}")


# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='为 Android APK 添加 APK Signature Scheme v2 签名'
    )
    parser.add_argument('--input', required=True, help='输入 APK 文件路径')
    parser.add_argument('--keystore', required=True, help='JKS keystore 文件路径')
    parser.add_argument('--alias', required=True, help='密钥别名')
    parser.add_argument('--storepass', required=True, help='Keystore 密码')
    parser.add_argument('--keypass', required=True, help='密钥密码')
    parser.add_argument('--output', required=True, help='输出 APK 文件路径')

    args = parser.parse_args()

    # 验证输入文件存在
    if not os.path.isfile(args.input):
        print(f"错误: 输入 APK 文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(args.keystore):
        print(f"错误: Keystore 文件不存在: {args.keystore}", file=sys.stderr)
        sys.exit(1)

    try:
        sign_apk(
            args.input, args.keystore, args.alias,
            args.storepass, args.keypass, args.output
        )
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
