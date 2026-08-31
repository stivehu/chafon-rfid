#!/usr/bin/env python

from datetime import datetime

from .base import G2InventoryResponse as BaseG2InventoryResponse, ReaderCommand, ReaderResponseFrame, Tag, TagData
from .command import G2_TAG_INVENTORY

G2_TAG_INVENTORY_PARAM_MEMORY_EPC = 0x01
G2_TAG_INVENTORY_PARAM_MEMORY_TID = 0x02
G2_TAG_INVENTORY_PARAM_MEMORY_USER = 0x03

G2_TAG_INVENTORY_PARAM_SESSION_S0 = 0x00
G2_TAG_INVENTORY_PARAM_SESSION_S1 = 0x01
G2_TAG_INVENTORY_PARAM_SESSION_S2 = 0x02
G2_TAG_INVENTORY_PARAM_SESSION_S3 = 0x03
G2_TAG_INVENTORY_PARAM_SESSION_SMART = 0xFF

G2_TAG_INVENTORY_PARAM_ANTENNA_1 = 0x80
G2_TAG_INVENTORY_PARAM_ANTENNA_2 = 0x81
G2_TAG_INVENTORY_PARAM_ANTENNA_3 = 0x82
G2_TAG_INVENTORY_PARAM_ANTENNA_4 = 0x83

G2_TAG_INVENTORY_PARAM_TARGET_A = 0x00
G2_TAG_INVENTORY_PARAM_TARGET_B = 0x01


class G2InventoryCommand(ReaderCommand):

    def __init__(self, addr=0xFF, q_value=15, deliver_statistics=0, strategy=0, fast_id=1,
                 session=G2_TAG_INVENTORY_PARAM_SESSION_S0, mask_source=G2_TAG_INVENTORY_PARAM_MEMORY_EPC,
                 target=G2_TAG_INVENTORY_PARAM_TARGET_A, antenna=G2_TAG_INVENTORY_PARAM_ANTENNA_1, scan_time=0x14,
                 adrTid=0, lenTid=6):
        # TODO check q_value in range 0 ~ 15, session 0 ~ 3
        mask_data = [0x00, 0x00, 0x00]
        # q_value_byte = (deliver_statistics << 7) + (strategy << 6) + (fast_id << 5) + q_value
        q_value_byte = 4
        if mask_source == G2_TAG_INVENTORY_PARAM_MEMORY_TID:
            cmd_data = [q_value_byte, session, mask_source] + mask_data + [adrTid, lenTid] + [target, antenna,
                                                                                              scan_time]
        else:
            cmd_data = [q_value_byte, session, mask_source] + mask_data + [target, antenna, scan_time]
        super(G2InventoryCommand, self).__init__(G2_TAG_INVENTORY, addr, data=cmd_data)


def _translate_antenna_num(antenna_code):
    if antenna_code == 1:
        return 1
    elif antenna_code == 2:
        return 2
    elif antenna_code == 4:
        return 3
    elif antenna_code == 8:
        return 4
    else:
        return None


class G2InventoryResponseFrame(ReaderResponseFrame):

    tag_prefix_bytes = 0
    tag_suffix_bytes = 1

    tag_data_prefix_bytes = 1 # Number of bytes before 'num tags' byte

    def __init__(self, resp_bytes, offset=0):
        super(G2InventoryResponseFrame, self).__init__(resp_bytes, offset)
        self.num_tags = 0
        self.antenna = 0
        if len(self.data) > self.tag_data_prefix_bytes:
            self.antenna = _translate_antenna_num(self.data[0])
            self.num_tags = self.data[1]

    def get_tag(self):
        tag_data_prefix_and_num_tags_bytes = self.tag_data_prefix_bytes + 1
        if len(self.data) > tag_data_prefix_and_num_tags_bytes:
            tag_data = TagData(self.data[self.tag_data_prefix_bytes:], prefix_bytes=self.tag_prefix_bytes, suffix_bytes=self.tag_suffix_bytes)
            for data_item in tag_data.get_tag_data():
                epc_value = data_item[1]
                rssi = data_item[2][0]
                yield Tag(epc_value, antenna_num=self.antenna, rssi=rssi)


class G2InventoryResponse(BaseG2InventoryResponse):

    frame_class = G2InventoryResponseFrame


def decode_rtc_timestamp(four_bytes):
    value = int.from_bytes(bytes(four_bytes), byteorder='big')
    second = value & 0x3F
    value >>= 6
    minute = value & 0x3F
    value >>= 6
    hour = value & 0x1F
    value >>= 5
    date = value & 0x1F
    value >>= 5
    month = value & 0x0F
    value >>= 4
    year = value & 0x3F
    return datetime(2000 + year, month, date, hour, minute, second)


def encode_rtc_datetime(dt):
    return [dt.year - 2000, dt.month, dt.day, dt.hour, dt.minute, dt.second]


def decode_antenna_bitmask(byte):
    return [ant for ant in range(1, 5) if byte & (1 << (ant - 1))]


class ReaderMemoryRecord(object):

    def __init__(self, disc_time, last_time, count, antennas, epc_or_tid):
        self.disc_time = disc_time
        self.last_time = last_time
        self.count = count
        self.antennas = antennas
        self.epc_or_tid = epc_or_tid


class ReaderMemoryResponseFrame(ReaderResponseFrame):

    record_header_bytes = 11  # DiscTime(4) + LastTime(4) + Count(2) + Ant(1)

    def get_records(self):
        offset = 0
        data = self.data
        while offset + self.record_header_bytes < len(data):
            disc_time = bytes(data[offset:offset + 4])
            last_time = bytes(data[offset + 4:offset + 8])
            count = (data[offset + 8] << 8) | data[offset + 9]
            antennas = decode_antenna_bitmask(data[offset + 10])
            offset += self.record_header_bytes
            tag_length = data[offset]
            offset += 1
            epc_or_tid = bytes(data[offset:offset + tag_length])
            offset += tag_length
            yield ReaderMemoryRecord(disc_time=disc_time, last_time=last_time, count=count,
                                      antennas=antennas, epc_or_tid=epc_or_tid)
