import schemdraw
import schemdraw.elements as elm
from schemdraw import dsp
from schemdraw import opamp
from schemdraw import flow
from schemdraw import diode
from schemdraw import led

with schemdraw.Drawing(file='circuit_diagram.svg', show=False, unit=3) as d:
    # 1. IR Emitter Block
    emitter = d.add(dsp.Box(w=4, h=2.5).label('IR Emitter'))
    
    # Dashed lines to represent the IR light path
    d.add(elm.Line().at(emitter.E).right().length(d.unit*1.5).linestyle('--').color('red'))
    d.add(elm.Arrow().at(emitter.E, (d.unit*1.5, 0)).right().length(d.unit*0.5).linestyle('--').color('red').label('IR Beam', loc='top', color='red'))
    d.add(elm.Line().at(emitter.E, (d.unit*2, 0)).tox(emitter.E.x + d.unit*2.5).toy(emitter.E.y - 2.5).linestyle('--').color('red'))
    
    # 2. Receiver & Amplifier Stage (Hierarchical Block)
    # The parent box for the stage
    receiver_box = d.add(flow.Box(w=11, h=7).label('Receiver & Amplifier Stage', loc='top').at(emitter.E, (d.unit*4, 0)).anchor('W'))

    # Components placed inside the parent box
    # Photodiode to detect reflected light
    pd_pos = receiver_box.W + (1, 0)
    d.add(elm.Arrow().at(pd_pos).left().length(d.unit*0.5).linestyle('--').color('red').label('Reflected IR', loc='top', color='red'))
    pd = d.add(diode.Photodiode().at(pd_pos).right().label('IR Sensor', loc='bottom'))
    
    # Transimpedance Amplifier (TIA) Opamp
    tia = d.add(opamp.Opamp().right().at(pd.end, (d.unit, 0)).anchor('in-'))
    d.add(elm.Line().endpoints(pd.end, tia.in_minus))
    d.add(elm.Line().at(tia.in_plus).down(d.unit*0.75))
    d.add(elm.Ground())
    
    # Output from the hierarchical block
    d.add(elm.Line().at(tia.out).to(receiver_box.E).label('V_sensor', loc='top'))

    # 3. Comparator Stage
    comp = d.add(opamp.Opamp().at(receiver_box.E, (d.unit*2, 0)).anchor('in+'))
    d.add(elm.Line().endpoints(receiver_box.E, comp.in_plus))

    # 4. Voltage Divider for Reference Voltage
    vdiv_start = comp.in_minus - (d.unit*2, 0)
    d.add(elm.Vdd().at(vdiv_start).up().label('VCC'))
    R1 = d.add(elm.Resistor().at(vdiv_start).down().label('R1', loc='left'))
    d.add(elm.Dot())
    R2 = d.add(elm.Resistor().down().label('R2', loc='left'))
    d.add(elm.Ground())
    
    # Connect reference voltage to the comparator's inverting input
    d.add(elm.Line().at(R1.end).to(comp.in_minus).label('V_ref', loc='bottom'))

    # 5. Output Indicator Stage
    out_start = d.add(elm.Dot().at(comp.out))
    R_led = d.add(elm.Resistor().at(out_start.start).right(d.unit*0.75).label('R_limit', loc='top'))
    L1 = d.add(led.LED().at(R_led.end).down().label('Object\nDetected', loc='bottom'))
    d.add(elm.Line().at(L1.end).to(L1.end-(0, d.unit*0.5)))
    d.add(elm.Ground())
    d.add(elm.Line().at(out_start.start).toy(R_led.start)) # Straighten line from opamp out