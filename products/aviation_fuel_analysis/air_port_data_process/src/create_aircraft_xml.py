#!/usr/bin/env python3
"""
创建常用机型的XML文件
"""

import os
import pyBADA

# 常用机型的参数数据
AIRCRAFT_DATA = {
    'A320': {
        'model': 'A320',
        'type': 'Turbofan',
        'engine': 'CFM56-5B4',
        'designator': 'A320',
        'WTC': 'M',
        'S': 122.6,
        'MTOW': 78000,
        'OEW': 42400,
        'MPL': 19500,
        'span': 34.1,
        'length': 37.6,
        'n_eng': 2,
        'hmo': 12497,
        'hmax': 12497,
        'mmo': 0.82,
        'vmo': 158.4,
        'TOL': 2090,
        'LDL': 1650
    },
    'A319': {
        'model': 'A319',
        'type': 'Turbofan',
        'engine': 'CFM56-5B6',
        'designator': 'A319',
        'WTC': 'M',
        'S': 122.6,
        'MTOW': 75500,
        'OEW': 40800,
        'MPL': 16800,
        'span': 34.1,
        'length': 33.8,
        'n_eng': 2,
        'hmo': 12497,
        'hmax': 12497,
        'mmo': 0.82,
        'vmo': 158.4,
        'TOL': 2090,
        'LDL': 1650
    },
    'A321': {
        'model': 'A321',
        'type': 'Turbofan',
        'engine': 'CFM56-5B1',
        'designator': 'A321',
        'WTC': 'M',
        'S': 122.6,
        'MTOW': 89000,
        'OEW': 48500,
        'MPL': 24500,
        'span': 34.1,
        'length': 44.5,
        'n_eng': 2,
        'hmo': 12497,
        'hmax': 12497,
        'mmo': 0.82,
        'vmo': 158.4,
        'TOL': 2090,
        'LDL': 1650
    },
    'B737': {
        'model': 'B737',
        'type': 'Turbofan',
        'engine': 'CFM56-7B24',
        'designator': 'B737',
        'WTC': 'M',
        'S': 124.6,
        'MTOW': 79000,
        'OEW': 41413,
        'MPL': 19300,
        'span': 34.3,
        'length': 39.5,
        'n_eng': 2,
        'hmo': 12497,
        'hmax': 12497,
        'mmo': 0.82,
        'vmo': 158.4,
        'TOL': 2316,
        'LDL': 1600
    },
    'B738': {
        'model': 'B738',
        'type': 'Turbofan',
        'engine': 'CFM56-7B26',
        'designator': 'B738',
        'WTC': 'M',
        'S': 124.6,
        'MTOW': 79000,
        'OEW': 41413,
        'MPL': 19300,
        'span': 34.3,
        'length': 39.5,
        'n_eng': 2,
        'hmo': 12497,
        'hmax': 12497,
        'mmo': 0.82,
        'vmo': 158.4,
        'TOL': 2316,
        'LDL': 1600
    },
    'B777': {
        'model': 'B777',
        'type': 'Turbofan',
        'engine': 'GE90-115B',
        'designator': 'B777',
        'WTC': 'H',
        'S': 427.8,
        'MTOW': 347815,
        'OEW': 155206,
        'MPL': 76000,
        'span': 64.8,
        'length': 73.9,
        'n_eng': 2,
        'hmo': 13106,
        'hmax': 13106,
        'mmo': 0.89,
        'vmo': 158.4,
        'TOL': 3200,
        'LDL': 2100
    },
    'E190': {
        'model': 'E190',
        'type': 'Turbofan',
        'engine': 'CF34-10E5',
        'designator': 'E190',
        'WTC': 'M',
        'S': 92.5,
        'MTOW': 51800,
        'OEW': 28500,
        'MPL': 11300,
        'span': 28.7,
        'length': 36.2,
        'n_eng': 2,
        'hmo': 12497,
        'hmax': 12497,
        'mmo': 0.82,
        'vmo': 158.4,
        'TOL': 2133,
        'LDL': 1365
    }
}

def create_aircraft_xml(aircraft_code, data):
    """创建单个机型的XML文件"""
    
    # 获取目标路径
    bada_path = os.path.dirname(pyBADA.__file__)
    target_dir = os.path.join(bada_path, 'aircraft', 'BADA3', 'BADA3', aircraft_code)
    xml_file = os.path.join(target_dir, f'{aircraft_code}.xml')
    
    # 确保目录存在
    os.makedirs(target_dir, exist_ok=True)
    
    # 创建XML内容
    xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<BADA3>
    <model>{data['model']}</model>
    <type>{data['type']}</type>
    <engine>{data['engine']}</engine>
    <ICAO>
        <designator>{data['designator']}</designator>
        <WTC>{data['WTC']}</WTC>
    </ICAO>
    
    <AFCM>
        <S>{data['S']}</S>
        <mref>{data['MTOW'] * 0.8}</mref>
        <Configuration HLid="0">
            <name>Clean</name>
            <LGUP>
                <DPM>
                    <CD>
                        <d>0.024</d>
                        <d>0.0530</d>
                    </CD>
                </DPM>
                <BLM_clean>
                    <VS>61.2</VS>
                    <CL_clean>
                        <Clbo>1.308</Clbo>
                        <k>0.5</k>
                    </CL_clean>
                </BLM_clean>
            </LGUP>
        </Configuration>
        <Configuration HLid="1">
            <name>Initial climb</name>
            <LGUP>
                <DPM>
                    <CD>
                        <d>0.027</d>
                        <d>0.0530</d>
                    </CD>
                </DPM>
                <BLM_clean>
                    <VS>61.2</VS>
                    <CL_clean>
                        <Clbo>1.308</Clbo>
                        <k>0.5</k>
                    </CL_clean>
                </BLM_clean>
            </LGUP>
        </Configuration>
        <Configuration HLid="2">
            <name>Cruise</name>
            <LGUP>
                <DPM>
                    <CD>
                        <d>0.024</d>
                        <d>0.0530</d>
                    </CD>
                </DPM>
                <BLM_clean>
                    <VS>61.2</VS>
                    <CL_clean>
                        <Clbo>1.308</Clbo>
                        <k>0.5</k>
                    </CL_clean>
                </BLM_clean>
            </LGUP>
        </Configuration>
        <Configuration HLid="3">
            <name>Approach</name>
            <LGUP>
                <DPM>
                    <CD>
                        <d>0.067</d>
                        <d>0.0530</d>
                    </CD>
                </DPM>
                <BLM_clean>
                    <VS>61.2</VS>
                    <CL_clean>
                        <Clbo>1.308</Clbo>
                        <k>0.5</k>
                    </CL_clean>
                </BLM_clean>
            </LGUP>
        </Configuration>
        <Configuration HLid="4">
            <name>Landing</name>
            <LGUP>
                <DPM>
                    <CD>
                        <d>0.105</d>
                        <d>0.0530</d>
                    </CD>
                </DPM>
                <BLM_clean>
                    <VS>61.2</VS>
                    <CL_clean>
                        <Clbo>1.308</Clbo>
                        <k>0.5</k>
                    </CL_clean>
                </BLM_clean>
            </LGUP>
        </Configuration>
    </AFCM>
    
    <APCM>
        <mass>
            <mmin>{data['OEW']}</mmin>
            <mmax>{data['MTOW']}</mmax>
            <mref>{data['MTOW'] * 0.8}</mref>
        </mass>
        <envelope>
            <hmo>{data['hmo']}</hmo>
            <hmax>{data['hmax']}</hmax>
            <mmo>{data['mmo']}</mmo>
            <vmo>{data['vmo']}</vmo>
        </envelope>
        <TSFC>
            <cf1>0.81</cf1>
            <cf2>1050</cf2>
            <cf3>0.0</cf3>
            <cf4>0.0</cf4>
        </TSFC>
        <Thrust>
            <CTc>
                <c1>32000</c1>
                <c2>50000</c2>
                <c3>0.4</c3>
                <c4>0.0</c4>
                <c5>0.0</c5>
            </CTc>
            <CTdes>
                <c1>0.3</c1>
                <c2>0.0</c2>
                <c3>0.0</c3>
                <c4>0.0</c4>
                <c5>0.0</c5>
            </CTdes>
        </Thrust>
    </APCM>
    
    <PFM>
        <n_eng>{data['n_eng']}</n_eng>
        <CT>
            <CTc1>32000</CTc1>
            <CTc2>50000</CTc2>
            <CTc3>0.4</CTc3>
            <CTc4>0.0</CTc4>
            <CTc5>0.0</CTc5>
            <CTdeslow>0.3</CTdeslow>
            <CTdeshigh>0.3</CTdeshigh>
            <CTdesapp>0.3</CTdesapp>
            <CTdesld>0.3</CTdesld>
            <Hpdes>3048</Hpdes>
        </CT>
        <CF>
            <Cf1>0.81</Cf1>
            <Cf2>1050</Cf2>
            <Cf3>0.0</Cf3>
            <Cf4>0.0</Cf4>
            <Cfcr>0.95</Cfcr>
        </CF>
    </PFM>
    
    <ALM>
        <GLM>
            <hmo>{data['hmo']}</hmo>
            <hmax>{data['hmax']}</hmax>
            <temp_grad>-0.0065</temp_grad>
            <mass_grad>-0.0065</mass_grad>
        </GLM>
        <KLM>
            <mmo>{data['mmo']}</mmo>
            <vmo>{data['vmo']}</vmo>
        </KLM>
        <DLM>
            <MTOW>{data['MTOW']}</MTOW>
            <OEW>{data['OEW']}</OEW>
            <MPL>{data['MPL']}</MPL>
        </DLM>
    </ALM>
    
    <GPF>
        <mass>
            <mmin>{data['OEW']}</mmin>
            <mmax>{data['MTOW']}</mmax>
            <mref>{data['MTOW'] * 0.8}</mref>
        </mass>
        <TOL>{data['TOL']}</TOL>
        <LDL>{data['LDL']}</LDL>
        <span>{data['span']}</span>
        <length>{data['length']}</length>
        <n_eng>{data['n_eng']}</n_eng>
        <H_max_to>3000</H_max_to>
        <H_max_ld>3000</H_max_ld>
        <T_max_to>35</T_max_to>
        <T_max_ld>35</T_max_ld>
        <V_stall_to>65</V_stall_to>
        <V_stall_ld>60</V_stall_ld>
        <k_to>1.2</k_to>
        <k_ld>1.3</k_ld>
    </GPF>
    
    <ARPM>
        <AeroConfSchedule>
            <AeroPhase>
                <name>Take off</name>
                <HLid>2</HLid>
                <LG>UP</LG>
            </AeroPhase>
            <AeroPhase>
                <name>Initial climb</name>
                <HLid>1</HLid>
                <LG>UP</LG>
            </AeroPhase>
            <AeroPhase>
                <name>Climb</name>
                <HLid>0</HLid>
                <LG>UP</LG>
            </AeroPhase>
            <AeroPhase>
                <name>Cruise</name>
                <HLid>0</HLid>
                <LG>UP</LG>
            </AeroPhase>
            <AeroPhase>
                <name>Descent</name>
                <HLid>0</HLid>
                <LG>UP</LG>
            </AeroPhase>
            <AeroPhase>
                <name>Approach</name>
                <HLid>3</HLid>
                <LG>UP</LG>
            </AeroPhase>
            <AeroPhase>
                <name>Landing</name>
                <HLid>4</HLid>
                <LG>UP</LG>
            </AeroPhase>
        </AeroConfSchedule>
        
        <SpeedScheduleList>
            <SpeedSchedule>
                <SpeedPhase>
                    <name>Climb</name>
                    <CAS1>250</CAS1>
                    <CAS2>300</CAS2>
                    <M>0.78</M>
                </SpeedPhase>
                <SpeedPhase>
                    <name>Cruise</name>
                    <CAS1>250</CAS1>
                    <CAS2>300</CAS2>
                    <M>0.78</M>
                </SpeedPhase>
                <SpeedPhase>
                    <name>Descent</name>
                    <CAS1>250</CAS1>
                    <CAS2>300</CAS2>
                    <M>0.78</M>
                </SpeedPhase>
            </SpeedSchedule>
        </SpeedScheduleList>
    </ARPM>
    
</BADA3>'''
    
    # 写入文件
    with open(xml_file, 'w', encoding='utf-8') as f:
        f.write(xml_content)
    
    print(f"✅ 创建XML文件: {xml_file}")
    return xml_file

def create_all_aircraft_xml():
    """创建所有机型的XML文件"""
    print("🔧 创建常用机型的XML文件")
    print("=" * 50)
    
    success_count = 0
    total_count = len(AIRCRAFT_DATA)
    
    for aircraft_code, data in AIRCRAFT_DATA.items():
        if create_aircraft_xml(aircraft_code, data):
            success_count += 1
    
    print(f"\n📊 创建完成: {success_count}/{total_count} 个机型")
    return success_count == total_count

if __name__ == "__main__":
    create_all_aircraft_xml() 