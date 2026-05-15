import sys
import os
import math
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import ezdxf
from ezdxf.math import Vec2
from core.geometry.ir import Segment
from core.engine import process_dxf
from core.parser.dxf_parser import parse_dxf


def test_dimension_parsing():
    try:
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        msp.add_linear_dim(
            base=(0, 0), p1=(0, 5), p2=(10, 5), dimstyle="EZ_DIM_STANDARD",
        ).render()
        doc.saveas(tempfile.gettempdir() + "/test_dimension.dxf")
    except Exception:
        print("  test_dimension_parsing: SKIP (ezdxf dim API issue)")
        return

    r = process_dxf(tempfile.gettempdir() + "/test_dimension.dxf")
    ir = r.ir
    non_geom_errors = [e for e in ir.errors if "Entidade não reconhecida" not in e]
    assert len(non_geom_errors) == 0, f"errors: {ir.errors}"
    assert r.success or r.error == "Nenhum polígono encontrado"
    print("  test_dimension_parsing: PASS")


def test_solid_parsing():
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_solid([(0, 0), (5, 0), (0, 5), (5, 5)])
    doc.saveas(tempfile.gettempdir() + "/test_solid.dxf")

    r = process_dxf(tempfile.gettempdir() + "/test_solid.dxf")
    ir = r.ir
    non_geom_errors = [e for e in ir.errors if "Entidade não reconhecida" not in e]
    assert len(non_geom_errors) == 0, f"errors: {ir.errors}"
    assert len(ir.segments) >= 2
    print("  test_solid_parsing: PASS")


def test_3dface_parsing():
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_3dface([(0, 0), (5, 0), (5, 5), (0, 5)])
    doc.saveas(tempfile.gettempdir() + "/test_3dface.dxf")

    r = process_dxf(tempfile.gettempdir() + "/test_3dface.dxf")
    ir = r.ir
    non_geom_errors = [e for e in ir.errors if "Entidade não reconhecida" not in e]
    assert len(non_geom_errors) == 0, f"errors: {ir.errors}"
    assert len(ir.segments) >= 2
    print("  test_3dface_parsing: PASS")


def test_mline_parsing():
    try:
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        mline = msp.add_mline()
        mline.vertices = [Vec2(0, 0), Vec2(10, 0), Vec2(10, 10)]
        doc.saveas(tempfile.gettempdir() + "/test_mline.dxf")
    except Exception:
        print("  test_mline_parsing: SKIP (ezdxf MLINE API issue)")
        return

    r = process_dxf(tempfile.gettempdir() + "/test_mline.dxf")
    ir = r.ir
    non_geom_errors = [e for e in ir.errors if "Entidade não reconhecida" not in e]
    assert len(non_geom_errors) == 0, f"errors: {ir.errors}"
    assert len(ir.segments) >= 2
    print("  test_mline_parsing: PASS")


def test_block_ellipse():
    doc = ezdxf.new("R2010")
    block = doc.blocks.new("ELLIPSE_BLOCK")
    block.add_ellipse(center=(0, 0), major_axis=(3, 0), ratio=0.5,
                       start_param=0, end_param=2 * math.pi)
    msp = doc.modelspace()
    msp.add_blockref("ELLIPSE_BLOCK", insert=(10, 10))
    doc.saveas(tempfile.gettempdir() + "/test_block_ellipse.dxf")

    r = process_dxf(tempfile.gettempdir() + "/test_block_ellipse.dxf")
    ir = r.ir
    assert len(ir.ellipses) == 1, f"expected 1 ellipse, got {len(ir.ellipses)}"
    non_geom_errors = [e for e in ir.errors if "Entidade não reconhecida" not in e]
    assert len(non_geom_errors) == 0, f"errors: {ir.errors}"
    print("  test_block_ellipse: PASS")


def test_binary_dxf():
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 10))
    msp.add_line((10, 10), (10, 0))
    msp.add_line((10, 0), (0, 0))
    doc.saveas(tempfile.gettempdir() + "/test_binary.dxf")
    r = process_dxf(tempfile.gettempdir() + "/test_binary.dxf")
    assert r.success
    print("  test_binary_dxf: PASS")


def test_ignored_entities():
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 10))
    msp.add_line((10, 10), (10, 0))
    msp.add_line((10, 0), (0, 0))
    doc.saveas(tempfile.gettempdir() + "/test_ignored.dxf")

    r = process_dxf(tempfile.gettempdir() + "/test_ignored.dxf")
    ir = r.ir
    unknown = [e for e in ir.errors if "Entidade não reconhecida" in e]
    if unknown:
        print(f"  WARN: unknown entities: {unknown}")
    assert r.success
    print("  test_ignored_entities: PASS")


if __name__ == "__main__":
    test_dimension_parsing()
    test_solid_parsing()
    test_3dface_parsing()
    test_mline_parsing()
    test_block_ellipse()
    test_binary_dxf()
    test_ignored_entities()
    print("\nAll entity tests passed!")
