// Marks the known reset path after importing the CS5211 serial-ROM firmware at address 0.
//@category CS5211

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class AnnotateCS5211 extends GhidraScript {
    @Override
    public void run() throws Exception {
        Address reset = toAddr(0x0000);
        Address main = toAddr(0x0130);
        Address panelConfig = toAddr(0x0110);
        Address profileTable = toAddr(0x0010);
        Address profileSelect = toAddr(0x0266);
        Address profileApply = toAddr(0x045b);
        Address bootTable = toAddr(0x0e1f);
        Address bootInterpreter = toAddr(0x0177);

        createLabel(reset, "Reset_Vector", true);
        createLabel(main, "Reset_Handler", true);
        createLabel(panelConfig, "Panel_Configuration_Constants", true);
        createLabel(profileTable, "GPIO_Profile_Table", true);
        createLabel(profileSelect, "Read_GPIO_Profile_Index", true);
        createLabel(profileApply, "Apply_GPIO_Profile", true);
        createLabel(bootTable, "Internal_RAM_Boot_Table", true);
        createLabel(bootInterpreter, "Interpret_Internal_RAM_Boot_Table", true);

        setPlateComment(reset,
            "CS5211 8051 firmware. Physical serial-ROM offset 0x1000 maps to this address. " +
            "The reset vector jumps to 0x0130.");
        setPlateComment(main,
            "Primary initialization path reached from the reset vector.");
        setPlateComment(panelConfig,
            "Compact startup constants. Code at 0x02c2 reads these bytes with MOVC and " +
            "copies them into CS5211 external-register addresses including 0x0602, 0x0603, " +
            "and 0x01d0–0x01f9. This is panel/bridge configuration, not an RGB LUT.");
        setPlateComment(profileTable,
            "Sixteen 16-byte profile records. Index derives from XDATA[0x00ca] low nibble. " +
            "All 16 records are identical in this ROM: profile selection currently changes nothing.");
        setPlateComment(profileSelect,
            "Reads XDATA[0x00ca] & 0x0f, shifts it left four bits, and stores the profile-table offset in RAM 0x08.");
        setPlateComment(profileApply,
            "Copies profile bytes at firmware 0x0010 + RAM[0x08] to XDATA 0x009f and 0x01dc–0x01f4. " +
            "These registers are the leading LVDS format/mapping candidates.");
        setPlateComment(bootTable,
            "Compact internal-RAM initialization table interpreted by code at 0x0177. " +
            "See scripts/decode_cs5211_boot_table.py for a checked decoder.");
    }
}
