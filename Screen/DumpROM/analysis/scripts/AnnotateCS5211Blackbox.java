// Names supported by the reproducible full-CPU experiments (2026-09-28).
//@category CS5211
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;

public class AnnotateCS5211Blackbox extends GhidraScript {
    private void name(long address, String name) throws Exception {
        Function f = getFunctionAt(toAddr(address));
        if (f == null) f = createFunction(toAddr(address), name);
        if (f != null) f.setName(name, SourceType.USER_DEFINED);
    }
    @Override
    public void run() throws Exception {
        disassemble(toAddr(0x0003));
        disassemble(toAddr(0x000b));
        disassemble(toAddr(0x0c48));
        Function isr = getFunctionAt(toAddr(0x0c48));
        if (isr != null && isr.getBody().getNumAddresses() <= 1) removeFunction(isr);
        name(0x0a20, "Configure_Clock_From_Ratio");
        name(0x0647, "Software_Float_Multiply");
        name(0x0750, "Software_Float_Divide");
        name(0x07ed, "Integer_To_Float_Chop");
        name(0x082b, "Float_To_Integer32");
        name(0x0879, "Float_Round_Half_Up_And_Pack");
        name(0x08ac, "Multiply16_Low16");
        name(0x08be, "Multiply32_Low32");
        name(0x0949, "Unsigned_Divide32");
        name(0x09e9, "Compare_Unsigned32");
        name(0x0c48, "Timer0_DutyCycle_ISR");
        name(0x0cbc, "Recover_Peripherals_If_Marker_Changed");
        name(0x0d30, "Poll_Brightness_Buttons");
        name(0x0d8d, "Poll_Power_Button");
        name(0x0dfc, "BusyWait_Units");
        name(0x0e5c, "Poll_Delay_And_Count_Timeout");
        name(0x0e7a, "Initialize_Timer0");
        setPlateComment(toAddr(0x0a20),
            "Executed with emu8051 and independently checked with uCsim. " +
            "Reads BE24 M from XDATA 0549..054b, N from 054c..054e, rate from 060a. " +
            "Computes integer (27*rate*M)/N for 25/50/100 thresholds, and approximately " +
            "458752*rate*M/N for output 0564..0566. R7 zero/nonzero selects divider " +
            "branch. Mvid/Nvid/pixel-clock interpretation strongly inferred; " +
            "peripheral semantics and LVDS mapping not emulated.");
        setEOLComment(toAddr(0x0511),
            "01f4 receives full profile[11] OR ((physical ROM[1122]&0x0f)<<4); profile is NOT masked.");
        setEOLComment(toAddr(0x049f),
            "Profile copy executes again after link recovery. GPIO selection was latched at startup.");
        setEOLComment(toAddr(0x03e4),
            "OR 1 makes following JNZ unconditional for every byte read from 0613.");
        setPlateComment(toAddr(0x07ed),
            "Application calls with A=0 for unsigned conversion. Normalization drops low mantissa bits without rounding. " +
            "Arithmetic helpers round halfway upward. Rational model matches 2048 wide-domain clock cases.");
        setEOLComment(toAddr(0x0c76),
            "Lookup IRAM[0x16 + level]. Unvalidated upper brightness bound can let buttons raise level above 10 and read outside 0x16..0x20.");
        println("Applied black-box-supported names and comments; no binary patch.");
    }
}
