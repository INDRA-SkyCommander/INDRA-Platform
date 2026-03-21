-- License.
--
-- Copyright 2018 PingguSoft <pinggusoft@gmail.com>
--
-- This program is free software: you can redistribute it and/or modify
-- it under the terms of the GNU General Public License as published by
-- the Free Software Foundation, either version 3 of the License, or
-- (at your option) any later version.
--
-- This program is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY; without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
-- GNU General Public License for more details.
--
-- You should have received a copy of the GNU General Public License
-- along with this program.  If not, see <http://www.gnu.org/licenses/>.
--

-- load the udp.port table
udp_table = DissectorTable.get("udp.port")
dissector = udp_table:get_dissector(8889)
if dissector ~= nil then
    udp_table:remove(8889, dissector)
    message("8889 dissector removed")
end

dissector = udp_table:get_dissector(11111)
if dissector ~= nil then
    udp_table:remove(11111, dissector)
    message("11111 dissector removed")
end


---------------------------------------------------------------------------------------------------
-- class definition
---------------------------------------------------------------------------------------------------
function class(base, init)
   local c = {}    -- a new class instance
   if not init and type(base) == 'function' then
      init = base
      base = nil
   elseif type(base) == 'table' then
    -- our new class is a shallow copy of the base class!
      for i,v in pairs(base) do
         c[i] = v
      end
      c._base = base
   end
   -- the class will be the metatable for all its objects,
   -- and they will look up their methods in it.
   c.__index = c

   -- expose a constructor which can be called by <classname>(<args>)
   local mt = {}
   mt.__call = function(class_tbl, ...)
   local obj = {}
   setmetatable(obj,c)
   if init then
      init(obj,...)
   else 
      -- make sure that any stuff from the base class is initialized!
      if base and base.init then
      base.init(obj, ...)
      end
   end
   return obj
   end
   c.init = init
   c.is_a = function(self, klass)
      local m = getmetatable(self)
      while m do 
         if m == klass then return true end
         m = m._base
      end
      return false
   end
   setmetatable(c, mt)
   return c
end

---------------------------------------------------------------------------------------------------
-- ByteBuffer class 
---------------------------------------------------------------------------------------------------
ByteBuffer = class(function(base, tvb)
    base.tvb = tvb
    base.pos = 0
    base.len = tvb:len()
end)

function ByteBuffer:getPos()
    return self.pos;
end

function ByteBuffer:getRemain()
    return self.len - self.pos;
end

function ByteBuffer:getByte()
    a = self.tvb(self.pos, 1):le_uint()
    self.pos = self.pos + 1
    return a;
end

function ByteBuffer:peekByte()
    a = self.tvb(self.pos, 1):le_uint()
    return a;
end

function ByteBuffer:getShort()
    a = self.tvb(self.pos, 2):le_uint()
    self.pos = self.pos + 2
    return a;
end

function ByteBuffer:getInt()
    a = self.tvb(self.pos, 4):le_uint()
    self.pos = self.pos + 4
    return a;
end

function ByteBuffer:getInt64()
    a = self.tvb(self.pos, 6):le_uint64()
    self.pos = self.pos + 6
    return a;
end

function ByteBuffer:getBytes(size)
    a = self.tvb(self.pos, size)
    self.pos = self.pos + size
    return a;
end

function ByteBuffer:peekBytes(start, size)
    a = self.tvb(start, size)
    return a;
end

function ByteBuffer:skip(size)
    self.pos = self.pos + size
end


---------------------------------------------------------------------------------------------------
-- tello command
---------------------------------------------------------------------------------------------------
-- ts = os.time(os.date("!*t"))
local tello_cmd = Proto("TELLO_CMD", "TELLO_CMD")

local cmd_names = {
    [17] =   "TELLO_CMD_SSID",
    [18] =   "TELLO_CMD_SET_SSID",
    [19] =   "TELLO_CMD_SSID_PASS",
    [20] =   "TELLO_CMD_SET_SSID_PASS",
    [21] =   "TELLO_CMD_REGION",
    [22] =   "TELLO_CMD_SET_REGION",
    [37] =   "TELLO_CMD_REQ_VIDEO_SPS_PPS",
    [48] =   "TELLO_CMD_TAKE_PICTURE",
    [49] =   "TELLO_CMD_SWITCH_PICTURE_VIDEO",
    [50] =   "TELLO_CMD_START_RECORDING",
    [52] =   "TELLO_CMD_SET_EV",
    [70] =   "TELLO_CMD_DATE_TIME",
    [80] =   "TELLO_CMD_STICK",
    [4176] = "TELLO_CMD_LOG_HEADER_WRITE",
    [4177] = "TELLO_CMD_LOG_DATA_WRITE",
    [4178] = "TELLO_CMD_LOG_CONFIGURATION",
    [26] =   "TELLO_CMD_WIFI_SIGNAL",
    [40] =   "TELLO_CMD_VIDEO_BIT_RATE",
    [53] =   "TELLO_CMD_LIGHT_STRENGTH",
    [69] =   "TELLO_CMD_VERSION_STRING",
    [71] =   "TELLO_CMD_ACTIVATION_TIME",
    [73] =   "TELLO_CMD_LOADER_VERSION",
    [86] =   "TELLO_CMD_STATUS",
    [4182] = "TELLO_CMD_ALT_LIMIT",
    [4183] = "TELLO_CMD_LOW_BATT_THRESHOLD",
    [4185] = "TELLO_CMD_ATT_ANGLE",
    [55] =   "TELLO_CMD_SET_JPEG_QUALITY",
    [84] =   "TELLO_CMD_TAKEOFF",
    [85] =   "TELLO_CMD_LANDING",
    [88] =   "TELLO_CMD_SET_HEIGHT",
    [92] =   "TELLO_CMD_FLIP",
    [93] =   "TELLO_CMD_THROW_FLY",
    [94] =   "TELLO_CMD_PALM_LANDING",
    [4180] = "TELLO_CMD_PLANE_CALIBRATION",
    [4181] = "TELLO_CMD_SET_LOW_BATTERY_THRESHOLD",
    [4184] = "TELLO_CMD_SET_ATTITUDE_ANGLE",
    [67] =   "TELLO_CMD_ERROR1",
    [68] =   "TELLO_CMD_ERROR2",
    [98] =   "TELLO_CMD_FILE_SIZE",
    [99] =   "TELLO_CMD_FILE_DATA",
    [100 ] = "TELLO_CMD_FILE_COMPLETE",
    [90] =   "TELLO_CMD_HANDLE_IMU_ANGLE",
    [32] =   "TELLO_CMD_SET_VIDEO_BIT_RATE",
    [33] =   "TELLO_CMD_SET_DYN_ADJ_RATE",
    [36] =   "TELLO_CMD_SET_EIS",
    [128 ] = "TELLO_CMD_SMART_VIDEO_START",
    [129 ] = "TELLO_CMD_SMART_VIDEO_STATUS",
    [4179] = "TELLO_CMD_BOUNCE",
}

local cmd_fields =
{
    pf_sop     = ProtoField.uint8("tello.sop",     "SOP   ", base.HEX, nil),
    pf_size    = ProtoField.uint16("tello.sz",     "SIZE  "),
    pf_crc8    = ProtoField.uint8("tello.crc8",    "CRC8  ", base.HEX, nil),
    pf_pacType = ProtoField.uint8("tello.pac",     "PACT  ", base.HEX, nil),
    pf_dir     = ProtoField.string("tello.dir",    "DIR   "),
    pf_cmdID   = ProtoField.uint16("tello.cmd",    "CMD   ", base.DEC, cmd_names),
    pf_seqID   = ProtoField.uint16("tello.seq",    "SEQ   "),
    pf_dataSize= ProtoField.uint16("tello.datasz", "DATASZ"),
    pf_data    = ProtoField.bytes("tello.data",    "DATA  ", base.SPACE, nil),
    pf_crc16   = ProtoField.uint16("tello.crc16",  "CRC16 ", base.HEX, nil),
    pf_log     = ProtoField.bytes("tello.log",     "LOG-PL", base.SPACE, nil),
    pf_logID   = ProtoField.uint16("tello.logid",  "LOGID "),
}

tello_cmd.fields = cmd_fields

function tello_cmd.dissector(tvb, pinfo, root)
    pinfo.cols.protocol = "TELLO_CMD"
    local size = 0
    local stick = 0
    local pktlen = tvb:reported_length_remaining()
    local tree = root:add(tello_cmd, tvb:range(0, pktlen))
    local data_tree;

    p = ByteBuffer(tvb) 
    sop = p:peekByte()
    if sop == 0xCC then
        tree:add(cmd_fields.pf_sop, p:getByte())
        tree:add_le(cmd_fields.pf_size, p:getShort())
        tree:add(cmd_fields.pf_crc8, p:getByte())
        pact = p:getByte();
        tree:add(cmd_fields.pf_pacType, pact)
        if bit.band(pact, 0x80) == 0x80 then
            dest = " <- FROM DRONE"
            from_drone = 1
        else
            dest = " -> TO DRONE"
            from_drone = 0
        end
        tree:add(cmd_fields.pf_dir, dest)

        cmd = p:getShort()
        tree:add_le(cmd_fields.pf_cmdID, cmd)
        tree:add_le(cmd_fields.pf_seqID, p:getShort())

        size = p:getRemain() - 2
        tree:add_le(cmd_fields.pf_dataSize, size)
        if size ~= 0 then
            payload = p:getBytes(size)
            data_tree = tree:add(cmd_fields.pf_data, payload)
            pl = ByteBuffer(payload)
-- stick command
            if cmd == 80 then
                stick = pl:getInt64()
                axis1 = stick:band(0x7ff):lower()
                stick = stick:rshift(11)
                axis2 = stick:band(0x7ff):lower()
                stick = stick:rshift(11)
                axis3 = stick:band(0x7ff):lower()
                stick = stick:rshift(11)
                axis4 = stick:band(0x7ff):lower()
                stick = stick:rshift(11)
                axis5 = stick:band(0x7ff):lower()
                stick_str = string.format("roll:%4d, pitch:%4d, thr:%4d, yaw:%4d, fastmode:%d", axis1, axis2, axis3, axis4, axis5)
                data_tree:add(payload, "STICK - " .. stick_str)
            elseif cmd == 98 and from_drone == 1 then
                fileType = pl:getByte()
                fileSize = pl:getInt()
                fileID   = pl:getShort()
                file_str = string.format("fileID:%d, fileType:%d, fileSize:%d", fileID, fileType, fileSize)
                data_tree:add(payload, "FILE INFO - " .. file_str)
            elseif cmd == 99 then
                if from_drone == 1 then
                    fileID   = pl:getShort()
                    pieceNum = pl:getInt()
                    seqNum   = pl:getInt()
                    length   = pl:getShort()
                    file_str = string.format("fileID:%d, pieceNum:%d, seqNum:%d, len:%d", fileID, pieceNum, seqNum, length)
                    data_tree:add(payload, "FILE DATA - " .. file_str)
                else
                    pl:getByte()
                    fileID = pl:getShort()
                    pieceNum = pl:getInt()
                    file_str = string.format("fileID:%d, pieceNum:%d", fileID, pieceNum)
                    data_tree:add(payload, "FILE ACK - " .. file_str)
                end
            elseif cmd == 128 then
                if from_drone == 0 then
                    code   = pl:getByte()
                    start  = bit.band(code, 0x01)
                    code   = bit.rshift(code, 2)
                    mode   = bit.band(code, 0x07)
                    data_tree:add(payload, "SMART_REC_CMD - " .. string.format("mode:%d, start:%d", mode, start))
                end
            elseif cmd == 129 then
                if from_drone == 1 then
                    code   = pl:getByte()
                    dummy  = bit.band(code, 0x07)
                    code   = bit.rshift(code, 3)
                    start  = bit.band(code, 0x03)
                    code   = bit.rshift(code, 2)
                    mode   = bit.band(code, 0x07)
                    data_tree:add(payload, "SMART_REC_ACK - " .. string.format("dummy:%d, mode:%d, start:%d", dummy, mode, start))
                end
            elseif cmd == 4177 and from_drone == 1 then
                while pl:getRemain() > 0 and pl:peekByte() ~= 0x55 do   -- skip abnormal magic byte
                    pl:getByte()
                end

                while pl:getRemain() > 10 do
                    log_start   = pl:getPos()
                    log_magic   = pl:getByte()                          -- 0x55 = 'U'
                    log_len     = pl:getShort()
                    pl:getByte()                                        -- skip 1 byte:hdr checksum
                    log_id      = pl:getShort()
                    log_tick    = pl:getInt()
                    log_xor_key = bit.band(log_tick, 0xff)
                    if log_magic == 0x55 and pl:getRemain() >= (log_len - 10) then
                        logp   = ByteBuffer(pl:peekBytes(log_start, log_len))
                        packet = ByteArray.new()
                        packet:set_size(log_len - 10)
                        
                        dec_log_size = log_len - 10;
                        logp:skip(10)
                        for k = 0, dec_log_size - 1, 1 do
                            packet:set_index(k, bit.bxor(logp:getByte(), log_xor_key))
                        end
                        log_tree = data_tree:add_le(cmd_fields.pf_logID, log_id)
                        log_tree:add(pl:peekBytes(log_start, log_len), "LOG - " .. string.format("ts:%d ID:%d(0x%x) len:%d", log_tick, log_id, log_id, log_len))
                        new_tvb  = ByteArray.tvb(packet, "DECRYPT-LOG");
                        log_tree:add(cmd_fields.pf_log, new_tvb(0, dec_log_size))
                    end
                    pl:skip(log_len - 10)
                end
            end
        end
        tree:add_le(cmd_fields.pf_crc16, p:getShort())
    end
end


---------------------------------------------------------------------------------------------------
-- tello video
---------------------------------------------------------------------------------------------------
local tello_video = Proto("TELLO_VIDEO", "TELLO_VIDEO")

local video_fields =
{
    pf_seq    = ProtoField.uint8("tellovid.seq",     "SEQ   "),
    pf_subseq = ProtoField.uint8("tellovid.subseq",  "SubSEQ"),
    pf_viddata= ProtoField.bytes("tellovid.data",    "DATA  ", base.SPACE, nil),
    pf_nal    = ProtoField.uint8("tellovid.nal",     "NAL   "),
}

tello_video.fields = video_fields


function tello_video.dissector(tvb, pinfo, root)
    pinfo.cols.protocol = "TELLO_VIDEO"

    local pktlen = tvb:reported_length_remaining()
    local tree = root:add(tello_video, tvb:range(0, pktlen))    
    local data_tree;
    
    p = ByteBuffer(tvb) 
    tree:add(video_fields.pf_seq, p:getByte())
        
    subseq = p:getByte()
    tree:add(video_fields.pf_subseq, bit.band(subseq, 0x7f))
    data_tree = tree:add(video_fields.pf_viddata, p:peekBytes(p:getPos(), pktlen - 2))

    mark = p:getInt()
    if mark == 0x01000000 then
        nal_type = bit.band(tvb(j,1):le_uint(), 0x1f)
        data_tree:add(video_fields.pf_nal, nal_type)
    end
end

-- register our protocol to handle
udp_table:add(8889, tello_cmd)
udp_table:add(11111, tello_video)