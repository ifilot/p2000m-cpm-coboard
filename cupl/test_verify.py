"""Regression tests for the CUPL source checker, including hardware-logic faults."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from verify import PLD_PATH, Source, inputs_for, output_byte, verify, verify_stock


class SourceVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PLD_PATH.read_text(encoding="ascii")

    def mutate(self, old, new):
        self.assertIn(old, self.source)
        return self.source.replace(old, new, 1)

    def test_video_window_rejects_expansion_ram_select(self):
        broken = self.mutate("# (CPM_MODE & CPM_RAM2 & !BANK_WINDOW);",
                             "# (CPM_MODE & (CPM_RAM2 # CPM_VIDEO) & !BANK_WINDOW);")
        with self.assertRaisesRegex(ValueError, "P7..P0 mismatch"):
            verify(Source(broken))

    def test_banked_window_never_selects_video(self):
        model = Source(self.source)
        for bank in range(1, 8):
            for address in (0x4000, 0x5000, 0x6000, 0x7000, 0x7800, 0x7fff):
                values = model.evaluate(inputs_for(address, MRQ_N=0), 1, bank, 1)
                page = sum(values[f"RA{bit}"] << (bit - 12) for bit in (12, 13, 14))
                self.assertEqual(values["RAMS3_N"], 0)
                self.assertEqual(values["RA15"], 0)
                self.assertNotEqual(page, 5)
            values = model.evaluate(inputs_for(0xf000, MRQ_N=0), 1, bank, 1)
            self.assertEqual(tuple(values[name] for name in ("RA14", "RA13", "RA12", "RA15")),
                             (1, 0, 1, 0))
        # Reintroduce rev 0.6 and prove that the independent video decoder
        # check catches the hardware failure, not just a changed truth table.
        broken = self.mutate("CPM_RA12 = A12 & !(BANK_WINDOW & A13);", "CPM_RA12 = A12;")
        with self.assertRaisesRegex(ValueError, "Expansion video overlap"):
            verify(Source(broken))

    def test_current_design(self):
        verify(Source(self.source))

    def test_stock_only_design_and_fault_detection(self):
        source = PLD_PATH.with_name("p2000m-stock-prom.pld").read_text(encoding="ascii")
        verify_stock(Source(source, stock=True))
        for old, new in (("RAMS3_N = 'b'1;", "RAMS3_N = 'b'0;"),
                         ("RA13 = A13;", "RA13 = !A13;"),
                         ("RA15 = P7_RAMS2;", "RA15 = A15;"),
                         ("P3_ROMS1_N = !NORMAL_MONITOR;", "P3_ROMS1_N = 'b'1;"),
                         ("RA12 = A12;", "RA12 = A12 & MRQ_N;"),
                         ("RA12 = A12;", "RA12 = A12 # CPM_MODE;")):
            with self.subTest(fault=new):
                self.assertIn(old, source)
                with self.assertRaises(ValueError):
                    verify_stock(Source(source.replace(old, new), stock=True))

    def test_sram_bank_outputs_in_all_variants(self):
        for filename, stock in (("p2000m-stock-prom.pld", True),
                                ("p2000m-stock-fast.pld", True)):
            source = PLD_PATH.with_name(filename).read_text(encoding="ascii")
            check = verify_stock if stock else verify
            check(Source(source, stock=stock))
            for name in ("A14_RAM", "A15_RAM", "A16_RAM"):
                equation = f"{name} = 'b'0;"
                for replacement in ("", f"{name} = 'b'1;", f"{name} = A14;"):
                    with self.subTest(filename=filename, output=name, fault=replacement):
                        self.assertIn(equation, source)
                        with self.assertRaisesRegex(ValueError, "Missing|SRAM bank address"):
                            check(Source(source.replace(equation, replacement), stock=stock))

    def test_banking_faults_are_detected(self):
        faults = (
            ("A14_RAM = BANK_WINDOW & BANK0;", "A14_RAM = BANK0;"),
            ("A16_RAM = BANK_WINDOW & BANK2;", "A16_RAM = 'b'0;"),
            ("(BANK0 # BANK1 # BANK2)", "'b'1"),
            ("& !A15 & A14;", "& A14;"),
            ("& CPM_RAM2 & !BANK_WINDOW", "& CPM_RAM2"),
            ("BANK1.d = A12;", "BANK1.d = !A12;"),
            ("BANK_EN.d = T_MODEL;", "BANK_EN.d = !T_MODEL;"),
            ("BANK2.ar = !RES_N;", "BANK2.ar = 'b'0;"),
            ("BANK0.ck = CPM_WRITE;", "BANK0.ck = !CPM_WRITE;"),
        )
        for old, new in faults:
            with self.subTest(fault=new):
                with self.assertRaises(ValueError):
                    verify(Source(self.mutate(old, new)))

    def test_stock_mode_matches_original_prom_dump_with_either_mrq_level(self):
        dump = (PLD_PATH.parent.parent / "literature/82s123_dump_mobo.bin").read_bytes()
        self.assertEqual(len(dump), 32)
        model = Source(self.source)
        for mrq in (0, 1):
            actual = bytes(output_byte(model.evaluate(inputs_for(block << 11, MRQ_N=mrq), 0))
                           for block in range(32))
            self.assertEqual(actual, dump)

    def test_hardware_faults_are_detected(self):
        faults = (
            ("RA15 = P7_RAMS2;", "RA15 = A15;", "Expansion RAMS2"),
            ("RAMS3_N    = !(MEM_CYCLE & SEL_RAM3);", "RAMS3_N = 'b'0;", "/RAMS3"),
            ("MEM_CYCLE = !MRQ_N;", "MEM_CYCLE = 'b'1;", "P7..P0"),
            ("PROM_ENABLE = !CPM_MODE # MEM_CYCLE;", "PROM_ENABLE = MEM_CYCLE;", "P7..P0"),
            ("CPM_RA13 = !A13;", "CPM_RA13 = A13;", "Translation|Expansion video"),
            ("A5 & !A4", "A5 & A4", "Clock"),
            ("CPM_MODE.d  = D7;", "CPM_MODE.d = !D7;", "Register data"),
            ("CPM_MODE.ar = !RES_N;", "CPM_MODE.ar = RES_N;", "Reset"),
            ("CPM_MODE.ck = CPM_WRITE;", "CPM_MODE.ck = !CPM_WRITE;", "Clock"),
        )
        for old, new, message in faults:
            with self.subTest(fault=new):
                with self.assertRaisesRegex(ValueError, message):
                    verify(Source(self.mutate(old, new)))

    def test_unsupported_or_invalid_source_is_rejected(self):
        faults = (
            ("RA12", "UNKNOWN", "pin assignments"),
            ("CPM_RA13 = !A13;", "CPM_RA13 = !MISSING;", "Undefined"),
            ("CPM_RA13 = !A13;", "CPM_RA13 = !CPM_RA13;", "feedback"),
            ("CPM_RA13 = !A13;", "CPM_RA13 = A13 + 1;", "Unsupported"),
            ("CPM_MODE.ck = CPM_WRITE;", "CPM_MODE.ce = CPM_WRITE;", "Unsupported"),
            ("PIN  1 = RES_N;", "PIN 1 = RES_N; PIN 1 = RES_N;", "Duplicate"),
            ("CPM_MODE.d  = D7;", "", "Missing"),
        )
        for old, new, message in faults:
            with self.subTest(fault=new):
                with self.assertRaisesRegex(ValueError, message):
                    Source(self.mutate(old, new))

    def test_precedence_parentheses_and_forward_references(self):
        source = self.source + "\nCHECK = !LATER & A5 # A6; LATER = A4;\n"
        model = Source(source)
        grouped = Source(source.replace("!LATER & A5 # A6", "!(LATER & (A5 # A6))"))
        for port in range(256):
            inputs = inputs_for(port)
            a4, a5, a6 = ((port >> bit) & 1 for bit in (4, 5, 6))
            self.assertEqual(model.evaluate(inputs, 0)["CHECK"], int((not a4 and a5) or a6))
            self.assertEqual(grouped.evaluate(inputs, 0)["CHECK"], int(not (a4 and (a5 or a6))))

    def test_dependencies_outside_truth_table_sweeps_are_rejected(self):
        faults = (
            ("SEL_VIDEO   = !CPM_MODE & NORMAL_VIDEO;",
             "SEL_VIDEO = (!CPM_MODE & NORMAL_VIDEO) # (CPM_MODE & T_MODEL);"),
            ("CPM_RA12 = A12 & !(BANK_WINDOW & A13);", "CPM_RA12 = (A12 & !(BANK_WINDOW & A13)) # D7;"),
            ("CPM_WRITE;", "CPM_WRITE # A11;"),
            ("CPM_MODE.d  = D7;", "CPM_MODE.d = D7 # T_MODEL;"),
            ("CPM_MODE.ar = !RES_N;", "CPM_MODE.ar = !RES_N # !MRQ_N;"),
        )
        for old, new in faults:
            with self.subTest(fault=new):
                with self.assertRaisesRegex(ValueError, "Untested input dependencies"):
                    Source(self.mutate(old, new))

    def test_optimized_python_still_rejects_broken_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.pld"
            path.write_text(self.mutate("CPM_RA13 = !A13;", "CPM_RA13 = A13;"))
            result = subprocess.run(
                [sys.executable, "-O", str(PLD_PATH.with_name("verify.py")), "--source", str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertRegex(result.stderr, "Translation mismatch|Expansion video")
            self.assertNotIn("source verified", result.stdout)


if __name__ == "__main__":
    unittest.main()
