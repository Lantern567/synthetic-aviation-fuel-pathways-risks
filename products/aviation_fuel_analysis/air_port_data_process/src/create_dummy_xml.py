#!/usr/bin/env python3
"""
创建符合pyBADA要求的DUMMY.xml文件
"""

import os
import pyBADA

def create_dummy_xml():
    """创建DUMMY.xml文件"""
    
    # 获取目标路径
    bada_path = os.path.dirname(pyBADA.__file__)
    target_dir = os.path.join(bada_path, 'aircraft', 'BADA3', 'BADA3', 'DUMMY')
    xml_file = os.path.join(target_dir, 'DUMMY.xml')
    
    # 确保目录存在
    os.makedirs(target_dir, exist_ok=True)
    
    # 创建XML内容（基于A320的典型参数）
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<BADA3>
    <model>A320</model>
    <type>Turbofan</type>
    <engine>CFM56-5B4</engine>
    <ICAO>
        <designator>A320</designator>
        <WTC>M</WTC>
    </ICAO>
    
    <AFCM>
        <S>122.6</S>
        <mref>64500</mref>
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
                        <d>0.070</d>
                        <d>0.0530</d>
                    </CD>
                </DPM>
                <BLM>
                    <VS>55.0</VS>
                </BLM>
            </LGUP>
        </Configuration>
        <Configuration HLid="2">
            <name>Take off</name>
            <LGDN>
                <DPM>
                    <CD>
                        <d>0.086</d>
                        <d>0.0530</d>
                    </CD>
                    <DeltaCD>0.018</DeltaCD>
                </DPM>
                <BLM>
                    <VS>49.0</VS>
                </BLM>
            </LGDN>
        </Configuration>
        <Configuration HLid="3">
            <name>Approach</name>
            <LGUP>
                <DPM>
                    <CD>
                        <d>0.113</d>
                        <d>0.0530</d>
                    </CD>
                </DPM>
                <BLM>
                    <VS>44.9</VS>
                </BLM>
            </LGUP>
        </Configuration>
        <Configuration HLid="4">
            <name>Landing</name>
            <LGDN>
                <DPM>
                    <CD>
                        <d>0.145</d>
                        <d>0.0530</d>
                    </CD>
                    <DeltaCD>0.018</DeltaCD>
                </DPM>
                <BLM>
                    <VS>40.1</VS>
                </BLM>
            </LGDN>
        </Configuration>
    </AFCM>
    
    <PFM>
        <n_eng>2</n_eng>
        <CT>
            <CTc1>23746</CTc1>
            <CTc2>72420</CTc2>
            <CTc3>0.73739</CTc3>
            <CTc4>15866</CTc4>
            <CTc5>0.73739</CTc5>
            <CTdeslow>0.95</CTdeslow>
            <CTdeshigh>0.95</CTdeshigh>
            <CTdesapp>0.30</CTdesapp>
            <CTdesld>0.30</CTdesld>
            <Hpdes>3048</Hpdes>
        </CT>
        <CF>
            <Cf1>0.73739</Cf1>
            <Cf2>1266.8</Cf2>
            <Cf3>0.95</Cf3>
            <Cf4>2500</Cf4>
            <Cfcr>0.95</Cfcr>
        </CF>
    </PFM>
    
    <ALM>
        <GLM>
            <hmo>12497</hmo>
            <hmax>12497</hmax>
            <temp_grad>-0.000518</temp_grad>
            <mass_grad>-0.000518</mass_grad>
        </GLM>
        <KLM>
            <mmo>0.82</mmo>
            <vmo>158.4</vmo>
        </KLM>
        <DLM>
            <MTOW>78000</MTOW>
            <OEW>42400</OEW>
            <MPL>19500</MPL>
        </DLM>
    </ALM>
    
    <Ground>
        <Dimensions>
            <span>34.1</span>
            <length>37.6</length>
        </Dimensions>
        <Runway>
            <TOL>2090</TOL>
            <LDL>1650</LDL>
        </Runway>
    </Ground>
    
    <ARPM>
        <AeroConfSchedule>
            <AeroPhase>
                <name>Take off</name>
                <HLid>2</HLid>
                <LG>DN</LG>
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
                <LG>DN</LG>
            </AeroPhase>
        </AeroConfSchedule>
        
        <SpeedScheduleList>
            <SpeedSchedule>
                <SpeedPhase>
                    <name>Climb</name>
                    <CAS1>158</CAS1>
                    <CAS2>300</CAS2>
                    <M>0.78</M>
                </SpeedPhase>
                <SpeedPhase>
                    <name>Cruise</name>
                    <CAS1>158</CAS1>
                    <CAS2>300</CAS2>
                    <M>0.78</M>
                </SpeedPhase>
                <SpeedPhase>
                    <name>Descent</name>
                    <CAS1>158</CAS1>
                    <CAS2>300</CAS2>
                    <M>0.78</M>
                </SpeedPhase>
            </SpeedSchedule>
        </SpeedScheduleList>
    </ARPM>
</BADA3>'''
    
    # 写入XML文件
    try:
        with open(xml_file, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        print(f"✅ 成功创建 {xml_file}")
        print(f"文件大小: {os.path.getsize(xml_file)} bytes")
        
        # 验证文件是否可以被XML解析器读取
        import xml.etree.ElementTree as ET
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            print(f"✅ XML文件格式验证成功，根元素: {root.tag}")
        except Exception as e:
            print(f"❌ XML文件格式验证失败: {e}")
            
    except Exception as e:
        print(f"❌ 创建XML文件失败: {e}")

if __name__ == "__main__":
    create_dummy_xml() 