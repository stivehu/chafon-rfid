from datetime import datetime

from chafon_rfid.base import CommandRunner, ReaderCommand
from chafon_rfid.transport import MockTransport
from chafon_rfid.uhfreader288m import (
    G2InventoryCommand, G2InventoryResponse, G2InventoryResponseFrame, ReaderMemoryResponseFrame,
    decode_antenna_bitmask, decode_rtc_timestamp, encode_rtc_datetime,
)

from chafon_rfid.command import CF_GET_READER_INFO, CF_OBTAIN_TAG_INFO_FROM_MEMORY, G2_TAG_INVENTORY

RESP_TAGS_1 = '1500010301010c0000000000000000000003136bb1a5'
RESP_TAGS_2 = '1500010301010c3039606303c74380001a055940f93e'
RESP_TAGS_3 = '1500010304010c49440000000000000a0003346425c0'
RESP_TAGS_4 = '0d000103010104003230386da3d2'
RESP_NO_TAGS = '0700010101001e4b'
RESP_MULTIPLE_TAGS = '2300010301020c0000000000000000000003136b0c0000000000000000000003146c70f2'


def test_tag_inventory():
    transport = MockTransport(bytearray.fromhex(RESP_TAGS_1))
    command = ReaderCommand(G2_TAG_INVENTORY)
    runner = CommandRunner(transport)
    frame = G2InventoryResponseFrame(runner.run(command))
    assert frame.result_status == 3
    assert frame.resp_cmd == 0x01
    assert frame.reader_addr == 0
    assert frame.antenna == 1
    assert frame.num_tags == 1
    tag = next(frame.get_tag())
    assert tag.epc == bytearray.fromhex('000000000000000000000313')
    assert tag.rssi == 0x6b
    assert tag.antenna_num == 1


def test_tag_inventory_ant3():
    transport = MockTransport(bytearray.fromhex(RESP_TAGS_3))
    command = ReaderCommand(G2_TAG_INVENTORY)
    runner = CommandRunner(transport)
    frame = G2InventoryResponseFrame(runner.run(command))
    assert frame.result_status == 3
    assert frame.resp_cmd == 0x01
    assert frame.reader_addr == 0
    assert frame.antenna == 3
    assert frame.num_tags == 1
    tag = next(frame.get_tag())
    assert tag.epc == bytearray.fromhex('49440000000000000a000334')
    assert tag.rssi == 0x64
    assert tag.antenna_num == 3


def test_multiple_tags():
    transport = MockTransport(bytearray.fromhex(RESP_MULTIPLE_TAGS))
    command = ReaderCommand(G2_TAG_INVENTORY)
    runner = CommandRunner(transport)
    response = G2InventoryResponse(runner.run(command))
    frame_generator = response.get_frame()
    frame = next(frame_generator)
    assert frame.result_status == 3
    assert frame.resp_cmd == 0x01
    assert frame.reader_addr == 0
    assert frame.antenna == 1
    assert frame.num_tags == 2
    tag_generator = frame.get_tag()
    tag1 = next(tag_generator)
    assert tag1.epc == bytearray.fromhex('000000000000000000000313')
    assert tag1.rssi == 0x6b
    assert tag1.antenna_num == 1
    tag2 = next(tag_generator)
    assert tag2.epc == bytearray.fromhex('000000000000000000000314')
    assert tag2.rssi == 0x6c
    assert tag2.antenna_num == 1


def test_inventory_command_defaults():

    command = G2InventoryCommand()
    assert command.data == list(bytearray.fromhex('0f0001000000008014'))


def test_inventory_command():

    command = G2InventoryCommand(q_value=2, session=1, mask_source=2, target=1, scan_time=3)
    assert command.data == list(bytearray.fromhex('020102000000018003'))


def test_decode_rtc_timestamp():
    assert decode_rtc_timestamp(bytearray.fromhex('60dec8b8')) == datetime(2024, 3, 15, 12, 34, 56)


def test_decode_rtc_timestamp_year_2000():
    assert decode_rtc_timestamp(bytearray.fromhex('00420000')) == datetime(2000, 1, 1, 0, 0, 0)


def test_decode_rtc_timestamp_year_2063_max_fields():
    assert decode_rtc_timestamp(bytearray.fromhex('ff3f7efb')) == datetime(2063, 12, 31, 23, 59, 59)


def test_encode_rtc_datetime():
    assert encode_rtc_datetime(datetime(2024, 3, 15, 12, 34, 56)) == [24, 3, 15, 12, 34, 56]


def test_encode_rtc_datetime_year_2000():
    assert encode_rtc_datetime(datetime(2000, 1, 1, 0, 0, 0)) == [0, 1, 1, 0, 0, 0]


def test_decode_antenna_bitmask_single_antennas():
    assert decode_antenna_bitmask(0x01) == [1]
    assert decode_antenna_bitmask(0x02) == [2]
    assert decode_antenna_bitmask(0x04) == [3]
    assert decode_antenna_bitmask(0x08) == [4]


def test_decode_antenna_bitmask_combinations():
    assert decode_antenna_bitmask(0x05) == [1, 3]
    assert decode_antenna_bitmask(0x0F) == [1, 2, 3, 4]
    assert decode_antenna_bitmask(0x00) == []


RESP_MEMORY_SINGLE_RECORD = '1700430060dec8b860dec8b800010106112233445566dd0d'
RESP_MEMORY_MORE_FRAMES = '1700430360dec8b860dec8b800020506112233445566ce70'
RESP_MEMORY_TWO_RECORDS = ('2900430060dec8b860dec8b80001010611223344556660dec8b8'
                            '60dec8b8000205061122334455666481')


def test_reader_memory_response_frame_single_record():
    transport = MockTransport(bytearray.fromhex(RESP_MEMORY_SINGLE_RECORD))
    command = ReaderCommand(CF_OBTAIN_TAG_INFO_FROM_MEMORY)
    runner = CommandRunner(transport)
    frame = ReaderMemoryResponseFrame(runner.run(command))
    assert frame.result_status == 0x00
    records = list(frame.get_records())
    assert len(records) == 1
    record = records[0]
    assert decode_rtc_timestamp(record.disc_time) == datetime(2024, 3, 15, 12, 34, 56)
    assert decode_rtc_timestamp(record.last_time) == datetime(2024, 3, 15, 12, 34, 56)
    assert record.count == 1
    assert record.antennas == [1]
    assert record.epc_or_tid == bytearray.fromhex('112233445566')


def test_reader_memory_response_frame_more_frames_status():
    transport = MockTransport(bytearray.fromhex(RESP_MEMORY_MORE_FRAMES))
    command = ReaderCommand(CF_OBTAIN_TAG_INFO_FROM_MEMORY)
    runner = CommandRunner(transport)
    frame = ReaderMemoryResponseFrame(runner.run(command))
    assert frame.result_status == 0x03
    record = next(frame.get_records())
    assert record.count == 2
    assert record.antennas == [1, 3]
    assert record.epc_or_tid == bytearray.fromhex('112233445566')


def test_reader_memory_response_frame_multiple_records():
    transport = MockTransport(bytearray.fromhex(RESP_MEMORY_TWO_RECORDS))
    command = ReaderCommand(CF_OBTAIN_TAG_INFO_FROM_MEMORY)
    runner = CommandRunner(transport)
    frame = ReaderMemoryResponseFrame(runner.run(command))
    assert frame.result_status == 0x00
    records = list(frame.get_records())
    assert len(records) == 2
    assert records[0].antennas == [1]
    assert records[1].antennas == [1, 3]
    assert records[1].count == 2
