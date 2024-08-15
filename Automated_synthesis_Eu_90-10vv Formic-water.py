import json

import numpy
from opentrons import types
from numpy import power, pi
import pandas as pd
from pathlib import Path
from opentrons.protocol_api import ProtocolContext
from opentrons.protocol_api.instrument_context import InstrumentContext
from opentrons.protocol_api.labware import Labware, Well
from opentrons.protocol_api._liquid import Liquid
from opentrons.protocol_api.module_contexts import ThermocyclerContext
from typing import List, Tuple, Dict
#from io import StringIO
import sys
sys.path.append('/var/lib/jupyter/notebooks/')

metadata = {
    "protocol.Name": "Automated synthesis of Eu-10F90W organometallic",
    "author": "Sina DT <sdehgha2@ncsu.edu>",
}
requirements = {
    "robotType": "OT-3",
    "apiLevel": "2.15"
}

input_data = pd.read_csv("/var/lib/jupyter/notebooks/hexane_formic_waste_volumes_v3.csv", index_col="well")

def run(pt: ProtocolContext) -> None:

    # pipette should start 10 mm below the hight
    def convert_volume_to_height(solvent_volume: float, labware_diameter: float) -> float:
        # volume should be in ul
        height = solvent_volume*4/(pi*power(labware_diameter, 2))
        return height

    def height_change(aspiration_volume: float, labware_diameter: float) -> float:
        delta_h = aspiration_volume*4/(pi*power(labware_diameter,2))
        return delta_h

    def set_rate_clearance(pipette: InstrumentContext, configure_volume: int = 500,
                           flow_rate_aspiration: int = 100, flow_rate_dispense: int = 300,
                           well_bottom_clearance_aspirate: int = 5, well_bottom_clearance_dispense: int = 10,
                           flow_rate_blow_out: int = 400) -> None:

        pipette.configure_for_volume(volume=configure_volume)
        pipette.flow_rate.aspirate = flow_rate_aspiration
        pipette.flow_rate.dispense = flow_rate_dispense
        pipette.well_bottom_clearance.aspirate = well_bottom_clearance_aspirate
        pipette.well_bottom_clearance.dispense = well_bottom_clearance_dispense
        pipette.flow_rate.blow_out = flow_rate_blow_out



    def mixing_process(repetitions: int, volume: float, loc: Well,rate: float = 1.0) -> None:
        p1000.mix(repetitions, volume, loc, rate)
        p1000.blow_out(loc)

    def rinsing(cleaning_agent_volume: float, cleaning_agent_loc: Well, bottom_clearance, cleaning_agent_dest: Well) -> None:

        pt.comment("-rising-")

        # transferring the cleaning_agent
        set_rate_clearance(pipette=p1000, configure_volume=900, flow_rate_aspiration=200,
                           flow_rate_dispense=500, well_bottom_clearance_aspirate=bottom_clearance,
                           well_bottom_clearance_dispense=30, flow_rate_blow_out=450)
        # ToDo: do something about cleaning agent height

        p1000.transfer(volume=cleaning_agent_volume, source=cleaning_agent_loc, dest=cleaning_agent_dest,
                       blowout_location="destination well", blow_out=True, touch_tip=True, new_tip="never")

        # mixing


        set_rate_clearance(pipette=p1000, configure_volume=950, flow_rate_aspiration=150,
                           flow_rate_dispense=550, well_bottom_clearance_aspirate=2,
                           well_bottom_clearance_dispense=25)

        mixing_process(repetitions=5, volume=900, loc=cleaning_agent_dest)

    def calculate_waste_volume(cleaning_agent_volume: float, mineral_oil_volume: float) -> float:
        waste_volume = cleaning_agent_volume + mineral_oil_volume+100
        return waste_volume

    # b: removing mineral oil and hexane mixture from source
    def remove_waste(cleaning_agent_volume: float, mineral_oil_vol: float, waste_source: Well,
                     waste_dump: Well) -> None:
        pt.comment("-removing waste-")

        waste_vol = calculate_waste_volume(cleaning_agent_volume=cleaning_agent_volume,
                                           mineral_oil_volume=mineral_oil_vol)

        set_rate_clearance(pipette=p1000, configure_volume=950, flow_rate_aspiration=150,
                           flow_rate_dispense=450, well_bottom_clearance_aspirate=.9,
                           well_bottom_clearance_dispense=60)

        p1000.transfer(volume=waste_vol, source=waste_source, dest=waste_dump,
                       blowout_location="destination well", blow_out=True, new_tip="never", touch_tip=True)

    # c: add formic acid_water mixture
    def add_reagent(reagent_volume: float, reagent_loc: Well, reagent_dest: Well, bottom_clearance) -> None:
        # put calculation of change of volume
        pt.comment(f"-adding reagent-")
        set_rate_clearance(pipette=p1000, configure_volume=1000, flow_rate_aspiration=150, flow_rate_dispense=400,
                           well_bottom_clearance_aspirate=bottom_clearance, well_bottom_clearance_dispense=40)
        p1000.transfer(volume=reagent_volume, source=reagent_loc, dest=reagent_dest,
                       blowout_location="destination well", blow_out=True, new_tip="once", touch_tip=True)

    def convert_name_to_vial(well_names: str) -> Well:
        wells: Well = tube_rack_4ml_24[well_names]
        return wells

    #determin the row type
    def extract_expt_params(row):
        solvent_volume = dict()
        for column_name, value in row.items():
            solvent_volume[column_name] = value
        return solvent_volume["cleaning_agent"], solvent_volume["reagent"]

    # write to read all the rows
    mineral_oil_volume = 800

    def perform_process(input_params: pd.DataFrame, initial_cleaning_agent_height, initial_reagent_height) -> None:
        next_reagent_height = initial_reagent_height
        next_cleaning_agent_height = initial_cleaning_agent_height
        vial_number = 1
        for vial_destination, additives in input_params.iterrows():

            cleaning_agent_vol, reagent_vol = extract_expt_params(additives)
            p1000.pick_up_tip()
            pt.comment(f"vial number: {vial_number}")
            # rinsing
            rinsing(cleaning_agent_volume=cleaning_agent_vol, cleaning_agent_loc=cleaning_agent,bottom_clearance=next_cleaning_agent_height,
                    cleaning_agent_dest=convert_name_to_vial(vial_destination))

            next_cleaning_agent_height -= height_change(cleaning_agent_vol, beaker_150ml_diameter)

            # removing waste
            remove_waste(cleaning_agent_volume=cleaning_agent_vol, mineral_oil_vol=mineral_oil_volume,
                         waste_source=convert_name_to_vial(vial_destination), waste_dump=waste)
            p1000.drop_tip()
            # adding reagents
            add_reagent(reagent_volume=reagent_vol, reagent_loc=reagent, bottom_clearance=next_reagent_height,
                        reagent_dest=convert_name_to_vial(vial_destination))
            next_reagent_height -= height_change(reagent_vol, beaker_150ml_diameter)
            vial_number+= 1





    # Labware labels
    beaker_rack_2_150ml_API: str = "ddomlab_2_tuberack_150000ul"
    beaker_rack_2_150ml_pos: str = "C1"

    # # formic
    beaker_rack_1_400ml_API: str = "ddomlab_1_tuberack_400000ul"
    beaker_rack_1_400ml_pos: str = "C2"
    tuberack_4ml_vial_API: str = "ddomlab_24_tuberack_4000ul"
    tuberack_4ml_vial_pos: str = "D1"
    thermocycler_API: str = "thermocycler module gen2"
    # tiprack_50_API: str = "opentrons_flex_96_tiprack_50ul"
    # tiprack_50_pos_1: str = "D1"
    # tiprack_50_pos_2: str = "C1"
    tiprack_1000_API: str = "opentrons_flex_96_tiprack_1000ul"
    tiprack_1000_pos_1: str = "D2"
    tiprack_1000_pos_2: str = "D3"

    # Labware positions
    reagent_loc: str = "A1"
    cleaning_agent_loc: str = "A2"
    waste_loc: str = "A1"






    # Load modules
    thermocycler: ThermocyclerContext = pt.load_module(thermocycler_API)

    tiprack_1000: List = [pt.load_labware(tiprack_1000_API, tiprack_1000_pos_1),
                          pt.load_labware(tiprack_1000_API, tiprack_1000_pos_2)]
    p1000: InstrumentContext = pt.load_instrument(
        "flex_1channel_1000", "right", tip_racks=tiprack_1000)
    # tiprack_50: List = [pt.load_labware(tiprack_50_API, tiprack_50_pos_1),
    #                     pt.load_labware(tiprack_50_API, tiprack_50_pos_2)]
    # p50: InstrumentContext = pt.load_instrument(
    #     "flex_1channel_50", "left", tip_racks=tiprack_50)


    # Volumes
    #height
    initial_total_cleaning_agent_volume: float = 80000
    initial_total_reagent_volume: float = 80000
    beaker_150ml_diameter:float = 52.71
    initial_cleaning_agent_height: float = convert_volume_to_height(initial_total_cleaning_agent_volume, beaker_150ml_diameter)-5
    initial_reagent_height: float = convert_volume_to_height(initial_total_reagent_volume, beaker_150ml_diameter)-5


    # Load labware
    beaker_rack_2_150ml: Labware = pt.load_labware(beaker_rack_2_150ml_API, beaker_rack_2_150ml_pos)
    beaker_rack_1_400ml: Labware = pt.load_labware(beaker_rack_1_400ml_API, beaker_rack_1_400ml_pos)
    tube_rack_4ml_24: Labware = pt.load_labware(tuberack_4ml_vial_API, tuberack_4ml_vial_pos)

    # material:~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    cleaning_agent: Well = beaker_rack_2_150ml[cleaning_agent_loc]
    reagent: Well = beaker_rack_2_150ml[reagent_loc]
    waste: Well = beaker_rack_1_400ml[waste_loc]


    # process


    perform_process(input_params=input_data,initial_cleaning_agent_height =initial_cleaning_agent_height,
                    initial_reagent_height=initial_reagent_height)

    pt.comment("finished")




