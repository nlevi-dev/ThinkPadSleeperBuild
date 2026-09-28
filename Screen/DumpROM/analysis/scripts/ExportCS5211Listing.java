// Export the current Ghidra 8051 listing for the CS5211 firmware.
//@category CS5211

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.Address;
import java.io.File;
import java.io.PrintWriter;

public class ExportCS5211Listing extends GhidraScript {
    @Override
    public void run() throws Exception {
        File output = new File(getScriptArgs().length > 0 ? getScriptArgs()[0] : "/tmp/cs5211-ghidra-listing.txt");
        try (PrintWriter out = new PrintWriter(output)) {
            out.println("Program: " + currentProgram.getName());
            out.println("Language: " + currentProgram.getLanguageID());
            out.println();
            out.println("FUNCTIONS");
            FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
            while (functions.hasNext()) {
                Function function = functions.next();
                out.printf("%s %s %s%n", function.getEntryPoint(), function.getName(), function.getBody());
            }
            out.println();
            out.println("INSTRUCTIONS");
            InstructionIterator instructions = currentProgram.getListing().getInstructions(true);
            while (instructions.hasNext()) {
                Instruction i = instructions.next();
                StringBuilder bytes = new StringBuilder();
                for (byte value : i.getBytes()) {
                    if (bytes.length() > 0) bytes.append(' ');
                    bytes.append(String.format("%02x", value & 0xff));
                }
                out.printf("%s  %-12s %s%n", i.getAddress(), bytes.toString(), i);
            }
        }
        println("Wrote " + output.getAbsolutePath());
    }
}
