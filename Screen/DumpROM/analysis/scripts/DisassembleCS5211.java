// Decode the CS5211 8051 firmware from its reset vector.
//@category CS5211

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class DisassembleCS5211 extends GhidraScript {
    @Override
    public void run() throws Exception {
        Address reset = toAddr(0x0000);
        Address main = toAddr(0x0130);
        disassemble(reset);
        disassemble(toAddr(0x0003));
        disassemble(toAddr(0x000b));
        createLabel(toAddr(0x000b), "Timer0_Vector", true);
        createFunction(toAddr(0x0c48), "Timer0_DutyCycle_ISR");
        createLabel(reset, "Reset_Vector", true);
        createLabel(main, "Reset_Handler", true);
        createFunction(reset, "Reset_Vector");
        createFunction(main, "Reset_Handler");
        println("Disassembled from " + reset);
    }
}
