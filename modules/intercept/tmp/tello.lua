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


-- tello command
ts = os.time(os.date("!*t"))
proto_name = "TELLO_CMD_" .. ts
local tello_cmd = Proto(proto_name, proto_name)
function tello_cmd.dissector(tvb, pinfo, tree)
    pinfo.cols.protocol = "TELLO_CMD"

    local i = 0
    local size = 0
    local st = tree:add(tello_cmd, tvb(), "TELLO_CMD : " .. tvb:len())
    local stick = 0

    sop = tvb(i,1):le_uint()
    if sop == 0xCC then
        st:add(tvb(i,1), "SOP:  " .. string.format("0x%2X", sop))
        i = i + 1
        st:add(tvb(i,2), "LEN:  " .. tvb(i,2):le_uint() / 8)
        i = i + 2
        st:add(tvb(i,1), "CRC8: " .. string.format("0x%02X", tvb(i,1):le_uint()))
        i = i + 1
        pact = tvb(i,1):le_uint()
        
        if bit.band(pact, 0x80) == 0x80 then
            dest = " <- FROM DRONE"
            from_drone = 1
        else
            dest = " -> TO DRONE"
            from_drone = 0
        end
        st:add(tvb(i,1), "PACT: " .. string.format("0x%02X", pact) .. dest)
        i = i + 1
        cmd = tvb(i,2):le_uint()
        st:add(tvb(i,2), "CMD:  " .. string.format("0x%04X = %d", cmd, cmd))
        i = i + 2
        st:add(tvb(i,2), "SEQ:  " .. string.format("0x%04X = %d", tvb(i,2):le_uint(), tvb(i,2):le_uint()))
        i = i + 2
        size = tvb:len() - i - 2
        if size ~= 0 then
            st:add(tvb(i,size), "DATA: " .. tvb(i,size))
            ii = i
-- stick command
            if cmd == 0x50 then
                stick = tvb(i,6):le_uint64()
                axis1 = stick:band(0x7ff):lower()
                stick = stick:rshift(11)
                axis2 = stick:band(0x7ff):lower()
                stick = stick:rshift(11)
                axis3 = stick:band(0x7ff):lower()
                stick = stick:rshift(11)
                axis4 = stick:band(0x7ff):lower()
                stick = stick:rshift(11)
                axis5 = stick:band(0x7ff):lower()
                
                stick_str = string.format("a1:%4d, a2:%4d, a3:%4d, a4:%4d, a5:%5d", axis1, axis2, axis3, axis4, axis5)
                st:add(tvb(i,size), "STICK: " .. stick_str)
            elseif cmd == 0x62 and from_drone == 1 then
                fileType = tvb(ii,1):le_uint()
                ii = ii + 1
                fileSize = tvb(ii,4):le_uint()
                ii = ii + 4
                fileID = tvb(ii,2):le_uint()
                ii = ii + 2
                file_str = string.format("fileID:%d, fileType:%d, fileSize:%d", fileID, fileType, fileSize)
                st:add(tvb(i,size), "FILE INFO: " .. file_str)
            elseif cmd == 0x63 then
                if from_drone == 1 then
                    fileID = tvb(ii,2):le_uint()
                    ii = ii + 2
                    pieceNum = tvb(ii,4):le_uint()
                    ii = ii + 4
                    seqNum = tvb(ii,4):le_uint()
                    ii = ii + 4
                    length = tvb(ii,2):le_uint()
                    file_str = string.format("fileID:%d, pieceNum:%d, seqNum:%d, len:%d", fileID, pieceNum, seqNum, length)
                    st:add(tvb(i,size), "FILE DATA: " .. file_str)
                else
                    ii = ii + 1
                    fileID = tvb(ii,2):le_uint()
                    ii = ii + 2
                    pieceNum = tvb(ii,4):le_uint()
                    ii = ii + 4
                    file_str = string.format("fileID:%d, pieceNum:%d", fileID, pieceNum)
                    st:add(tvb(i,size), "FILE ACK: " .. file_str)
                end
            end
            i = i + size
        end
        st:add(tvb(i,2), "CRC16: " .. string.format("0x%04X", tvb(i,2):le_uint()))
        i = i + 2
    end
end


-- tello video
proto_name = "TELLO_VIDEO_" .. ts
local tello_video = Proto(proto_name, proto_name)
function tello_video.dissector(tvb, pinfo, tree)
    pinfo.cols.protocol = "TELLO_VIDEO"

    local i = 0
    local size = 0;
    local st = tree:add(tello_video, tvb(), "TELLO_VIDEO : " .. tvb:len())

    st:add(tvb(i,1), "SEQ: " .. string.format("%d", tvb(i,1):le_uint()))
    i = i + 1
    subseq = tvb(i,1):le_uint()
    if bit.band(subseq, 0x80) == 0x80 then
        st:add(tvb(i,1), "SUB: " .. string.format("%d", bit.band(subseq, 0x7f)) .. " Last")
    else
        st:add(tvb(i,1), "SUB: " .. string.format("%d", bit.band(subseq, 0x7f)))
    end
    
    i = i + 1
    mark = tvb(i,4):le_int();
    i = i + 4
    if mark == 0x01000000 then
        nal_type = bit.band(tvb(i,1):le_uint(), 0x1f)
        st:add(tvb(i,1), "NAL TYPE: " .. string.format("%d", nal_type))
    end
end

-- register our protocol to handle
udp_table:add(8889, tello_cmd)
udp_table:add(11111, tello_video)