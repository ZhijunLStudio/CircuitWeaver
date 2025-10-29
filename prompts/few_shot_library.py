# This file contains a library of high-quality, verified code examples.
# These examples will be used as few-shot prompts to guide the Coder Agent.

EXAMPLE_1_HYBRID_SYSTEM = """
# CODE EXAMPLE 1: Advanced Hybrid System Block Diagram
import schemdraw
import schemdraw.elements as elm
from schemdraw import dsp
from schemdraw import logic
from schemdraw import flow

with schemdraw.Drawing(file='example_1_hybrid_system.svg', show=False, unit=2.5) as d:
    # ----------------------------------------------------
    # 1. Analog Front-End
    # ----------------------------------------------------
    d.add(elm.Line().left().label('Analog In', loc='left'))
    buf = d.add(elm.Opamp().label('Buffer'))
    d.add(elm.Arrow().right())
    filt_aa = d.add(dsp.Filter(response='lp').label('Anti-Alias\nFilter'))
    d.add(elm.Arrow().right())
    adc = d.add(dsp.Adc().label('ADC'))

    # ----------------------------------------------------
    # 2. Digital Core (as a nested ElementDrawing)
    # ----------------------------------------------------
    with schemdraw.Drawing(show=False) as d_core:
        # Define a custom DSP chip with various pins
        DSP_CHIP = (elm.Ic(pins=[
                        elm.IcPin(name='I2S_IN', side='left'),
                        elm.IcPin(name='I2S_OUT', side='right'),
                        elm.IcPin(name='A[0..15]', side='top', anchorname='ADDR'),
                        elm.IcPin(name='D[0..15]', side='top', anchorname='DATA'),
                        elm.IcPin(name='GPIO', side='bot')],
                    pinspacing=1.5)
                    .label('DSP Core', loc='center'))
        
        d_core.add(DSP_CHIP)
        
        # External Memory
        MEM = d_core.add(elm.Ic(pins=[
                        elm.IcPin(name='A[0..15]', side='bot', anchorname='ADDR'),
                        elm.IcPin(name='D[0..15]', side='bot', anchorname='DATA')],
                        pinspacing=1.5).at((DSP_CHIP.ADDR.x, DSP_CHIP.ADDR.y + 4)))
        
        # Address and Data Buses connecting DSP and Memory
        d_core.add(elm.BusLine(endpoints=DSP_CHIP.ADDR, to=MEM.ADDR))
        d_core.add(elm.BusLine(endpoints=DSP_CHIP.DATA, to=MEM.DATA))
        
        # Define input/output anchors for the entire block
        d_core.here = DSP_CHIP.I2S_IN
        d_core.set_anchor('digital_in')
        d_core.here = DSP_CHIP.I2S_OUT
        d_core.set_anchor('digital_out')

    # Add the digital core block to the main drawing
    digital_core_block = d.add(elm.ElementDrawing(d_core).at(adc.out).anchor('digital_in'))
    
    # Label the data bus between ADC and the core
    d.add(elm.Line().endpoints(adc.out, digital_core_block.digital_in)
              .linestyle('--').color('blue').label('I²S Data', loc='bottom', color='blue'))

    # ----------------------------------------------------
    # 3. Analog Back-End
    # ----------------------------------------------------
    dac = d.add(dsp.Dac().at(digital_core_block.digital_out).label('DAC'))
    d.add(elm.Arrow().at(dac.out).right())
    filt_recon = d.add(dsp.Filter(response='lp').label('Reconstruction\nFilter'))
    d.add(elm.Arrow().right())
    out_buf = d.add(elm.Opamp().label('Output\nDriver'))
    d.add(elm.Line().at(out_buf.out).right().label('Analog Out', loc='right'))
"""

EXAMPLE_2_ABSTRACTIONS = """
# CODE EXAMPLE 2: Sub-structures and Ellipsis Notation (Corrected)
import schemdraw
import schemdraw.elements as elm
from schemdraw import flow
from schemdraw import logic

with schemdraw.Drawing(file='example_2_abstractions.svg', show=False) as d:
    d.config(unit=2)
    
    # ----------------------------------------------------
    # 1. Series Ellipsis (e.g., a resistor ladder)
    # ----------------------------------------------------
    d.add(elm.Line().left(d.unit/2))
    R1 = d.add(elm.Resistor().label('R1'))
    R2 = d.add(elm.Resistor().label('R2'))
    dots = d.add(elm.DotDotDot(l=d.unit*0.5))
    RN = d.add(elm.Resistor().label('RN'))
    d.add(elm.Line().right(d.unit/2))

    # ----------------------------------------------------
    # 2. Parallel Ellipsis (e.g., parallel capacitors)
    # ----------------------------------------------------
    start_node = d.add(elm.Dot().at((R1.start.x, R1.start.y - 4)))
    end_node = d.add(elm.Dot().at((RN.end.x, RN.end.y - 4)))
    
    d.add(elm.Line().endpoints(start_node.center, end_node.center))
    
    with schemdraw.Drawing(show=False) as d_para:
        d_para.add(elm.Capacitor().up().label('C1'))
        d_para.add(elm.Capacitor().at((2,0)).up().label('C2'))
        d_para.add(elm.DotDotDot().at((3.5, 0.5)))
        d_para.add(elm.Capacitor().at((5,0)).up().label('CN'))
    
    para_group = d.add(elm.ElementDrawing(d_para).at((start_node.center.x + 1, start_node.center.y)))

    # ----------------------------------------------------
    # 3. Sub-structure pointing to a parent block
    # ----------------------------------------------------
    block_center_x = (R2.end.x + RN.start.x) / 2
    parent_box = d.add(flow.Box(w=5, h=3).at((block_center_x, R2.end.y + 5)).label('Main Controller'))

    # The detailed sub-structure drawn separately
    with schemdraw.Drawing(show=False) as d_sub:
        first_element = d_sub.add(logic.And().label('A1'))
        d_sub.add(logic.Line().right())
        d_sub.add(logic.Or().label('O1'))
        d_sub.add(logic.Not().right())
        
        d_sub.here = first_element.in1
        d_sub.set_anchor('start')
    
    sub_structure = d.add(elm.ElementDrawing(d_sub).at((parent_box.E.x + 4, parent_box.center.y)))
    
    # *** THE DEFINITIVE FIX: 'arrow' is a constructor parameter, not a method. ***
    d.add(elm.Annotate(arrow='->')
          .at(parent_box.E)
          .to(sub_structure.start)
          .label('Internal Logic Detail')
          .linestyle('--'))
"""

EXAMPLE_3_IC_POWER = """
# CODE EXAMPLE 3: IC with Power Rails and Signal Flow (Corrected)
import schemdraw
import schemdraw.elements as elm

with schemdraw.Drawing(file='example_3_ic_power.svg', show=False, fontsize=12) as d:
    # ----------------------------------------------------
    # 1. Power Rails
    # ----------------------------------------------------
    vcc_line = d.add(elm.Line().right(d.unit*6).at((0, 4)))
    d.add(elm.Vdd().at(vcc_line.start).label('+5V'))
    
    gnd_line = d.add(elm.Line().right(d.unit*6).at((0, 0)))
    d.add(elm.Ground().at(gnd_line.start))

    # ----------------------------------------------------
    # 2. The Microcontroller IC
    # ----------------------------------------------------
    # *** FIX: Use explicit keyword arguments for all .pin() calls for robustness ***
    MCU_def = (elm.Ic(size=(6, 5))
               .pin(name='VCC', side='top', pin='7')
               .pin(name='GND', side='bot', pin='8')
               .pin(name='RESET', side='left', pin='1', invert=True)
               .pin(name='XTAL1', side='left', pin='9')
               .pin(name='PWM_OUT', side='right', pin='11')
               .pin(name='LED_DRV', side='right', pin='13')
               .pin(name='I2C_SDA', side='right', pin='27') # Removed problematic 'arrow' argument
               .pin(name='I2C_SCL', side='right', pin='28'))

    MCU = d.add(MCU_def)
    MCU.label('ATmega328P', loc='center')

    # ----------------------------------------------------
    # 3. Connections
    # ----------------------------------------------------
    # Connect power
    d.add(elm.Line().up().at(MCU.VCC).toy(vcc_line.center).dot())
    d.add(elm.Line().right().tox(vcc_line.center))
    d.add(elm.Line().down().at(MCU.GND).toy(gnd_line.center).dot())
    d.add(elm.Line().right().tox(gnd_line.center))
    
    # Input circuit (Pull-up resistor on RESET)
    d.add(elm.Resistor().left().at(MCU.RESET).label('10kΩ'))
    d.add(elm.Line().up().toy(vcc_line.center).dot())
    d.add(elm.Line().right().tox(vcc_line.center))
    
    # Output circuit (LED)
    d.add(elm.Resistor().right().at(MCU.LED_DRV).label('330Ω'))
    d.add(elm.LED().down().label('STATUS'))
    d.add(elm.Ground())
"""