#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import csv
import json
import os
import re
import string

from collections import OrderedDict
from shutil import copyfile, rmtree

import pdb

EXT = '.txt'
DEFAULT_TEXT_LABEL = ''
ENTRY_LINE_BREAK = '\n=============================\n'
EDIT_THIS = '<EDIT_THIS>'

ROW_INDEX = '_Id'
EMBLEM_N = 'EMBLEM_NAME_'
EMBLEM_P = 'EMBLEM_PHONETIC_'

TEXT_LABEL = 'TextLabel'
TEXT_LABEL_JP = 'TextLabelJP'
TEXT_LABEL_DICT = {}

SKILL_DATA_NAME = 'SkillData'
SKILL_DATA_NAMES = None

ORDERING_DATA = {}

ROMAN_NUMERALS = [None, 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']
ELEMENT_TYPE = [None, 'Flame', 'Water', 'Wind', 'Light', 'Shadow']
CLASS_TYPE = [None, 'AttQack', 'Defense', 'Support', 'Healing']
WEAPON_TYPE = [None, 'Sword', 'Blade', 'Dagger', 'Axe', 'Lance', 'Bow', 'Wand', 'Staff']
QUEST_TYPE_DICT = {
    '1'   : 'Campaign',
    '201' : 'Event',
    '202' : 'Event',
    '203' : 'Event',
    '210' : 'Event',
    '211' : 'Event',
    '300' : 'Event',
    '204' : 'Raid',
    '208' : 'Facility',
}

GROUP_TYPE_DICT = {
    '1' : 'Campaign',
    '2' : 'Event',
}

MATERIAL_NAME_LABEL = 'MATERIAL_NAME_'
EVENT_RAID_ITEM_LABEL = 'EV_RAID_ITEM_NAME_'

class DataParser:
    def __init__(self, _data_name, _template, _formatter, _process_info):
        self.data_name = _data_name
        self.template = _template
        self.formatter = _formatter
        self.process_info = _process_info
        self.row_data = []
        self.extra_data = {}

    def process_csv(self, file_name, func):
        with open(in_dir+file_name+EXT, 'r', newline='', encoding='utf-8') as in_file:
            reader = csv.DictReader(in_file)
            for row in reader:
                if row[ROW_INDEX] == '0':
                    continue
                try:
                    func(row, self.row_data)
                except TypeError:
                    func(row, self.row_data, self.extra_data)
                # except Exception as e:
                #     print('Error processing {}: {}'.format(file_name, str(e)))

    def process(self):
        try: # process_info is an iteratable of (file_name, process_function)
            for file_name, func in self.process_info:
                self.process_csv(file_name, func)
        except TypeError: # process_info is the process_function
            self.process_csv(self.data_name, self.process_info)

    def emit(self, out_dir):
        with open(out_dir+self.data_name+EXT, 'w', newline='', encoding='utf-8') as out_file:
            for display_name, row in self.row_data:
                out_file.write(self.formatter(row, self.template, display_name))

def csv_as_index(path, index=None, value_key=None, tabs=False):
    with open(path, 'r', newline='', encoding='utf-8') as csvfile:
        if tabs:
            reader = csv.DictReader(csvfile, dialect='excel-tab')
        else:
            reader = csv.DictReader(csvfile)
        first_row = next(reader)
        key_iter = iter(first_row.keys())
        csvfile.seek(0)
        if not index:
            index = next(key_iter) # get first key as index
        if len(first_row) == 2:
            # load 2 column files as dict[string] = string
            value_key = next(key_iter) # get second key
        if value_key:
            return {row[index]: row[value_key] for row in reader if row[index] != '0'}
        else:
            # load >2 column files as a dict[string] = OrderedDict
            return {row[index]: row for row in reader if row[index] != '0'}

def get_label(key, lang='en'):
    try:
        txt_label = TEXT_LABEL_DICT[lang]
    except KeyError:
        txt_label = TEXT_LABEL_DICT['en']
    return txt_label[key].replace('\\n', ' ') if key in txt_label else DEFAULT_TEXT_LABEL

def get_jp_epithet(emblem_id):
    if 'jp' in TEXT_LABEL_DICT:
        return '{{' + 'Ruby|{}|{}'.format(get_label(EMBLEM_N + emblem_id, lang='jp'), get_label(EMBLEM_P + emblem_id, lang='jp')) + '}}'
    return ''

# All process_* functions take in 1 parameter (OrderedDict row) and return 3 values (OrderedDict new_row, str template_name, str display_name)
# Make sure the keys are added to the OrderedDict in the desired output order
def process_AbilityLimitedGroup(row, existing_data):
    new_row = OrderedDict()
    for k, v in row.items():
        new_row[k.strip('_')] = v
    new_row['AbilityLimitedText'] = get_label(row['_AbilityLimitedText']).format(ability_limit0=row['_MaxLimitedValue'])
    existing_data.append((None, new_row))

def process_AbilityShiftGroup(row, existing_data, ability_shift_groups):
    ability_shift_groups[row[ROW_INDEX]] = row

def process_AbilityData(row, existing_data, ability_shift_groups):
    new_row = OrderedDict()

    new_row['Id'] = row[ROW_INDEX]
    new_row['PartyPowerWeight'] = row['_PartyPowerWeight']
    new_row['GenericName'] = '' # EDIT_THIS

    shift_value = 0
    try:
        shift_group = ability_shift_groups[row['_ShiftGroupId']]
        for i in range(1, int(shift_group['_AmuletEffectMaxLevel']) + 1):
            if shift_group['_Level{}'.format(i)] == row[ROW_INDEX]:
                shift_value = i
                break
    except KeyError:
        shift_value = int(row['_ShiftGroupId'])

    # TODO: figure out what actually goes to {ability_val0}
    ability_value = EDIT_THIS if row['_AbilityType1UpValue'] == '0' else row['_AbilityType1UpValue']
    new_row['Name'] = get_label(row['_Name']).format(
        ability_shift0  =   ROMAN_NUMERALS[shift_value], # heck
        ability_val0    =   ability_value)

    # _ElementalType seems unreliable, use (element) in _Name for now
    detail_label = get_label(row['_Details'])
    if '{element_owner}' in detail_label and ')' in new_row['Name']:
        element = new_row['Name'][1:new_row['Name'].index(')')]
    else:
        element = ELEMENT_TYPE[int(row['_ElementalType'])]
    new_row['Details'] = detail_label.format(
        ability_cond0   =   row['_ConditionValue'],
        ability_val0    =   ability_value,
        element_owner   =   element)

    new_row['AbilityIconName'] = row['_AbilityIconName']
    new_row['AbilityGroup'] = row['_ViewAbilityGroupId1']
    new_row['AbilityLimitedGroupId1'] = row['_AbilityLimitedGroupId1']
    new_row['AbilityLimitedGroupId2'] = row['_AbilityLimitedGroupId2']
    new_row['AbilityLimitedGroupId3'] = row['_AbilityLimitedGroupId3']
    existing_data.append((new_row['Name'], new_row))

def process_AmuletData(row, existing_data):
    ABILITY_COUNT = 3
    FLAVOR_COUNT = 5
    new_row = OrderedDict()

    new_row['Id'] = row[ROW_INDEX]
    new_row['BaseId'] = row['_BaseId']
    new_row['Name'] = get_label(row['_Name'])
    new_row['NameJP'] = get_label(row['_Name'], lang='jp')
    new_row['FeaturedCharacters'] = '' # EDIT_THIS
    new_row['Obtain'] = '' # EDIT_THIS
    new_row['ReleaseDate'] = '' # EDIT_THIS
    new_row['Availability'] = '' # EDIT_THIS
    new_row['Rarity'] = row['_Rarity']
    new_row['AmuletType'] = CLASS_TYPE[int(row['_AmuletType'])]
    new_row['MinHp'] = row['_MinHp']
    new_row['MaxHp'] = row['_MaxHp']
    new_row['MinAtk'] = row['_MinAtk']
    new_row['MaxAtk'] = row['_MaxAtk']
    new_row['VariationId'] = row['_VariationId']
    for i in range(1, ABILITY_COUNT+1):
        for j in range(1, ABILITY_COUNT+1):
            ab_k = 'Abilities{}{}'.format(i, j)
            new_row[ab_k] = row['_' + ab_k]
    for i in range(1, ABILITY_COUNT+1):
        new_row['Ability{}Event'.format(i)] = 0
    new_row['ArtistCV'] = '' # EDIT_THIS
    for i in range(1, FLAVOR_COUNT+1):
        new_row['FlavorText{}'.format(i)] = get_label(row['_Text{}'.format(i)])
    new_row['IsPlayable'] = row['_IsPlayable']
    new_row['SellCoin'] = row['_SellCoin']
    new_row['SellDewPoint'] = row['_SellDewPoint']

    existing_data.append((new_row['Name'], new_row))

def process_Material(row, existing_data):
    new_row = OrderedDict()

    new_row['Id'] = row[ROW_INDEX]
    new_row['Name'] = get_label(row['_Name'])
    new_row['Description'] = get_label(row['_Detail'])
    try:
        new_row['Rarity'] = row['_MaterialRarity']
    except KeyError:
        new_row['Rarity'] = '' # EDIT_THIS
    if '_EventId' in row:
        new_row['QuestEventId'] = row['_EventId']
        new_row['SortId'] = row[ROW_INDEX]
    elif '_RaidEventId' in row:
        new_row['QuestEventId'] = row['_RaidEventId']
        new_row['SortId'] = row[ROW_INDEX]
    elif '_QuestEventId' in row:
        new_row['QuestEventId'] = row['_QuestEventId']
        new_row['Category'] = row['_Category']
        new_row['SortId'] = row['_SortId']
    new_row['Obtain'] = '\n*' + get_label(row['_Description'])
    new_row['Usage'] = '' # EDIT_THIS
    new_row['MoveQuest1'] = row['_MoveQuest1']
    new_row['MoveQuest2'] = row['_MoveQuest2']
    new_row['MoveQuest3'] = row['_MoveQuest3']
    new_row['MoveQuest4'] = row['_MoveQuest4']
    new_row['MoveQuest5'] = row['_MoveQuest5']
    new_row['PouchRarity'] = row['_PouchRarity']

    try:
        new_row['Exp'] = row['_Exp']
        # new_row['Plus'] = row['_Plus'] # augments
    except KeyError:
        pass

    existing_data.append((new_row['Name'], new_row))

def process_CharaData(row, existing_data):
    new_row = OrderedDict()

    new_row['IdLong'] = row[ROW_INDEX]
    new_row['Id'] = row['_BaseId']
    new_row['Name'] = get_label(row['_Name'])
    new_row['FullName'] = get_label(row['_SecondName'])
    new_row['NameJP'] = get_label(row['_Name'], lang='jp')
    new_row['Title'] = get_label(EMBLEM_N + row['_EmblemId'])
    new_row['TitleJP'] = get_jp_epithet(row['_EmblemId'])
    new_row['Obtain'] = '' # EDIT_THIS
    new_row['ReleaseDate'] = '' # EDIT_THIS
    new_row['Availability'] = '' # EDIT_THIS
    new_row['WeaponType'] = WEAPON_TYPE[int(row['_WeaponType'])]
    new_row['Rarity'] = row['_Rarity']
    new_row['Gender'] = '' # EDIT_THIS
    new_row['Race'] = '' # EDIT_THIS
    new_row['ElementalType'] = ELEMENT_TYPE[int(row['_ElementalType'])]
    new_row['CharaType'] = CLASS_TYPE[int(row['_CharaType'])]
    new_row['VariationId'] = row['_VariationId']
    for stat in ('Hp', 'Atk'):
        for i in range(3, 6):
            min_k = 'Min{}{}'.format(stat, i)
            new_row[min_k] = row['_' + min_k]
        max_k = 'Max{}'.format(stat)
        new_row[max_k] = row['_' + max_k]
        for i in range(0, 5):
            plus_k = 'Plus{}{}'.format(stat, i)
            new_row[plus_k] = row['_' + plus_k]
        mfb_k = 'McFullBonus{}5'.format(stat)
        new_row[mfb_k] = row['_' + mfb_k]
    new_row['MinDef'] = row['_MinDef']
    new_row['DefCoef'] = row['_DefCoef']
    try:
        new_row['Skill1Name'] = get_label(SKILL_DATA_NAMES[row['_Skill1']])
        new_row['Skill2Name'] = get_label(SKILL_DATA_NAMES[row['_Skill2']])
    except KeyError:
        pass

    for i in range(1, 4):
        for j in range(1, 5):
            ab_k = 'Abilities{}{}'.format(i, j)
            new_row[ab_k] = row['_' + ab_k]
    for i in range(1, 6):
        ex_k = 'ExAbilityData{}'.format(i)
        new_row[ex_k] = row['_' + ex_k]
    new_row['ManaCircleName'] = row['_ManaCircleName']
    new_row['JapaneseCV'] = get_label(row['_CvInfo'])
    new_row['EnglishCV'] = get_label(row['_CvInfoEn'])
    new_row['Description'] = get_label(row['_ProfileText'])
    new_row['IsPlayable'] = row['_IsPlayable']
    new_row['MaxFriendshipPoint'] = row['_MaxFriendshipPoint']

    existing_data.append((new_row['Name'] + ' - ' + new_row['FullName'], new_row))

def process_SkillDataNames(row, existing_data):
    for idx, (name, chara) in enumerate(existing_data):
        for i in (1, 2):
            sn_k = 'Skill{}Name'.format(i)
            if chara[sn_k] == row[ROW_INDEX]:
                chara[sn_k] = get_label(row['_Name'])
                existing_data[idx] = (name, chara)

def process_Dragon(row, existing_data):
    new_row = OrderedDict()

    new_row['Id'] = row[ROW_INDEX]
    new_row['BaseId'] = row['_BaseId']
    new_row['Name'] = get_label(row['_Name'])
    new_row['FullName'] = get_label(row['_SecondName'])
    new_row['NameJP'] = get_label(row['_Name'], lang='jp')
    new_row['Title'] = get_label(EMBLEM_N + row['_EmblemId'])
    new_row['TitleJP'] = get_jp_epithet(row['_EmblemId'])
    new_row['Obtain'] = '' # EDIT_THIS
    new_row['ReleaseDate'] = '' # EDIT_THIS
    new_row['Availability'] = '' # EDIT_THIS
    new_row['Rarity'] = row['_Rarity']
    new_row['Gender'] = '' # EDIT_THIS
    new_row['ElementalType'] = ELEMENT_TYPE[int(row['_ElementalType'])]
    new_row['VariationId'] = row['_VariationId']
    new_row['IsPlayable'] = row['_IsPlayable']
    new_row['MinHp'] = row['_MinHp']
    new_row['MaxHp'] = row['_MaxHp']
    new_row['MinAtk'] = row['_MinAtk']
    new_row['MaxAtk'] = row['_MaxAtk']
    new_row['SkillName'] = get_label(SKILL_DATA_NAMES[row['_Skill1']])
    for i in (1, 2):
        for j in (1, 2):
            ab_k = 'Abilities{}{}'.format(i, j)
            new_row[ab_k] = row['_' + ab_k]
    new_row['ProfileText'] = get_label(row['_Profile'])
    new_row['FavoriteType'] = row['_FavoriteType']
    new_row['JapaneseCV'] = get_label(row['_CvInfo'])
    new_row['EnglishCV'] = get_label(row['_CvInfoEn'])
    new_row['SellCoin'] = row['_SellCoin']
    new_row['SellDewPoint'] = row['_SellDewPoint']
    new_row['MoveSpeed'] = row['_MoveSpeed']
    new_row['DashSpeedRatio'] = row['_DashSpeedRatio']
    new_row['TurnSpeed'] = row['_TurnSpeed']
    new_row['IsTurnToDamageDir'] = row['_IsTurnToDamageDir']
    new_row['MoveType'] = row['_MoveType']
    new_row['IsLongRange'] = row['_IsLongLange']
    new_row['AttackModifiers'] = '\n{{DragonAttackModifierRow|Combo 1|<EDIT_THIS>%|<EDIT_THIS>}}\n{{DragonAttackModifierRow|Combo 2|<EDIT_THIS>%|<EDIT_THIS>}}\n{{DragonAttackModifierRow|Combo 3|<EDIT_THIS>%|<EDIT_THIS>}}'
    existing_data.append((new_row['Name'], new_row))

def process_ExAbilityData(row, existing_data):
    new_row = OrderedDict()

    new_row['Id'] = row[ROW_INDEX]
    new_row['Name'] = get_label(row['_Name'])
    # guess the generic name by chopping off the last word, which is usually +n% or V
    new_row['GenericName'] = new_row['Name'][0:new_row['Name'].rfind(' ')]
    new_row['Details'] = get_label(row['_Details']).format(
        value1=row['_AbilityType1UpValue0']
    )
    new_row['AbilityIconName'] = row['_AbilityIconName']
    new_row['Category'] = row['_Category']
    new_row['PartyPowerWeight'] = row['_PartyPowerWeight']

    existing_data.append((new_row['Name'], new_row))

event_emblem_pattern = re.compile(r'^A reward from the ([A-Z].*?) event.$')
def process_EmblemData(row, existing_data):
    new_row = OrderedDict()

    new_row['Title'] = get_label(row['_Title'])
    new_row['TitleJP'] = get_jp_epithet(row['_Id'])
    new_row['Icon'] = 'data-sort-value ="{0}" | [[File:Icon_Profile_0{0}_Frame.png|28px|center]]'.format(row['_Rarity'])
    new_row['Text'] = get_label(row['_Gettext'])
    res = event_emblem_pattern.match(new_row['Text'])
    if res:
        new_row['Text'] = 'A reward from the [[{}]] event.'.format(res.group(1))

    existing_data.append((new_row['Title'], new_row))

def process_FortPlantDetail(row, existing_data, fort_plant_detail):
    try:
        fort_plant_detail[row['_AssetGroup']].append(row)
    except KeyError:
        fort_plant_detail[row['_AssetGroup']] = [row]

def process_FortPlantData(row, existing_data, fort_plant_detail):
    new_row = OrderedDict()

    new_row['Id'] = row[ROW_INDEX]
    new_row['Name'] = get_label(row['_Name'])
    new_row['Description'] = get_label(row['_Description'])
    new_row['Type'] = '' # EDIT_THIS
    new_row['Size'] = '{w}x{w}'.format(w=row['_PlantSize'])
    new_row['Available'] = '1'
    new_row['Obtain'] = '' # EDIT_THIS
    new_row['ReleaseDate'] = '' # EDIT_THIS
    new_row['ShortSummary'] = '' # EDIT_THIS

    # TODO: extract UpgradeTable from details
    images = []
    for detail in fort_plant_detail[row[ROW_INDEX]]:
        if len(images) == 0 or images[-1][1] != detail['_ImageUiName']:
            images.append((detail['_Level'], detail['_ImageUiName']))
    if len(images) > 1:
        new_row['Images'] = '{{#tag:tabber|\nLv' + \
            '\n{{!}}-{{!}}\n'.join(
            ['{}=\n[[File:{}.png|120px]]'.format(lvl, name) for lvl, name in images]) + \
            '}}'
    elif len(images) == 1:
        new_row['Images'] = '[[File:{}.png|120px]]'.format(images[0][1])
    else:
        new_row['Images'] = ''
    new_row['UpgradeTable'] = ''
    existing_data.append((new_row['Name'], new_row))

def process_SkillData(row, existing_data):
    new_row = OrderedDict()

    new_row['SkillId']= row[ROW_INDEX]
    new_row['Name']= get_label(row['_Name'])
    new_row['SkillLv1IconName']= row['_SkillLv1IconName']
    new_row['SkillLv2IconName']= row['_SkillLv2IconName']
    new_row['SkillLv3IconName']= row['_SkillLv3IconName']
    new_row['Description1']= get_label(row['_Description1'])
    new_row['Description2']= get_label(row['_Description2'])
    new_row['Description3']= get_label(row['_Description3'])
    new_row['HideLevel3']= '' # EDIT_THIS
    new_row['Sp']= row['_Sp']
    new_row['SpLv2']= row['_SpLv2']
    new_row['SpRegen']= '' # EDIT_THIS
    new_row['IsAffectedByTension']= row['_IsAffectedByTension']
    new_row['ZoominTime']= row['_ZoominTime']
    new_row['Zoom2Time']= row['_Zoom2Time']
    new_row['ZoomWaitTime']= row['_ZoomWaitTime']

    existing_data.append((new_row['Name'], new_row))

def process_MissionData(row, existing_data):
    entity_type_dict = {
        "2" : [get_label("USE_ITEM_NAME_" + row['_EntityId']),
                row['_EntityQuantity']],
        "4" : ["Rupies", row['_EntityQuantity']],
        "8" : [get_label("MATERIAL_NAME_" + row['_EntityId']),
                row['_EntityQuantity']],
        "10": ["Epithet: {}".format(get_label(EMBLEM_N + row['_EntityId'])),
                    "Rank="],
        "11": [get_label("STAMP_NAME_" + row['_EntityId']),
                row['_EntityQuantity']],
        "14": ["Eldwater", row['_EntityQuantity']],
        "16": ["Skip Ticket", row['_EntityQuantity']],
        "17": [get_label("SUMMON_TICKET_NAME_" + row['_EntityId']),
                row['_EntityQuantity']],
        "18": ["Mana", row['_EntityQuantity']],
        "23": ["Wyrmite", row['_EntityQuantity']],
    }

    new_row = [get_label(row['_Text'])]
    try:
        new_row.extend(entity_type_dict[row['_EntityType']])
    except KeyError:
        pass

    existing_data.append((new_row[0], new_row))

def process_QuestData(row, existing_data):
    new_row = {}
    for quest_type_id_check,quest_type in QUEST_TYPE_DICT.items():
        if row['_Id'].startswith(quest_type_id_check):
            new_row['QuestType'] = quest_type
            break
    new_row['Id'] = row[ROW_INDEX]
    new_row['_Gid'] = row['_Gid']
    new_row['QuestGroupName'] = get_label(row['_QuestViewName']).partition(':')
    if not new_row['QuestGroupName'][1]:
        new_row['QuestGroupName'] = ''
    else:
        new_row['QuestGroupName'] = new_row['QuestGroupName'][0]
    try:
        new_row['GroupType'] = GROUP_TYPE_DICT[row['_GroupType']]
    except KeyError:
        pass
    new_row['EventName'] = get_label('EVENT_NAME_{}'.format(row['_Gid']))
    new_row['SectionName'] = get_label(row['_SectionName'])
    new_row['QuestViewName'] = get_label(row['_QuestViewName'])
    # Case when quest has no elemental type
    try:
        new_row['Elemental'] = ELEMENT_TYPE[int(row['_Elemental'])]
        new_row['ElementalId'] = int(row['_Elemental'])
    except IndexError:
        new_row['Elemental'] = ''
        new_row['ElementalId'] = 0
    # process_QuestMight
    if row['_DifficultyLimit'] == '0':
        new_row['SuggestedMight'] = row['_Difficulty']
    else:
        new_row['MightRequirement'] = row['_DifficultyLimit']

    # process_QuestSkip
    if row['_SkipTicketCount'] == '1':
        new_row['SkipTicket'] = 'Yes'
    elif row['_SkipTicketCount'] == '-1':
        new_row['SkipTicket'] = ''

    new_row['NormalStaminaCost'] = row['_PayStaminaSingle']
    new_row['CampaignStaminaCost'] = row['_CampaignStaminaSingle']
    new_row['GetherwingCost'] = row['_PayStaminaMulti']
    new_row['CampaignGetherwingCost'] = row['_CampaignStaminaMulti']
    new_row['ClearTermsType'] = get_label('QUEST_CLEAR_CONDITION_{}'.format(row['_ClearTermsType']))

    row_failed_terms_type = row['_FailedTermsType']
    row_failed_terms_type = "0" if row_failed_terms_type == "6" else row_failed_terms_type
    new_row['FailedTermsType'] = get_label('QUEST_FAILURE_CONDITON_{}'.format(row_failed_terms_type))
    if row['_FailedTermsTimeElapsed'] != '0':
        new_row['TimeLimit'] = row['_FailedTermsTimeElapsed']

    new_row['ContinueLimit'] = row['_ContinueLimit']
    new_row['ThumbnailImage'] = row['_ThumbnailImage']
    new_row['DropRewards'] = ''
    new_row['WeaponRewards'] = ''
    new_row['WyrmprintRewards'] = ''
    new_row['ShowEnemies'] = 1
    new_row['AutoPlayType'] = row['_AutoPlayType']

    existing_data.append((new_row['QuestViewName'], new_row))

def process_QuestRewardData(row, existing_data):
    QUEST_FIRST_CLEAR_COUNT = 5
    QUEST_COMPLETE_COUNT = 3
    reward_template = '\n{{{{DropReward|droptype=First|itemtype={}|item={}|exact={}}}}}'

    found = False
    for index,existing_row in enumerate(existing_data):
        if existing_row[1]['Id'] == row[ROW_INDEX]:
            found = True
            break
    assert(found)

    curr_row = existing_row[1]
    first_clear_dict = {
        '8': reward_template.format(
            'Material', get_label('{}{}'.format(MATERIAL_NAME_LABEL, row['_FirstClearSetEntityId1'])), row['_FirstClearSetEntityQuantity1']),
        '20': reward_template.format(
            'Material', get_label('{}{}'.format(EVENT_RAID_ITEM_LABEL, row['_FirstClearSetEntityId1'])), row['_FirstClearSetEntityQuantity1']),
        '23': reward_template.format('Currency', 'Wyrmite', row['_FirstClearSetEntityQuantity1'])
    }
    complete_type_dict = {
        '1' : (lambda x: 'Don\'t allow any of your team to fall in battle' if x == '0' else 'Allow no more than {} of your team to fall in battle'.format(x)),
        '15': (lambda x: 'Don\'t use any continues'),
        '18': (lambda x: 'Finish in {} seconds or less'.format(x))
    }
    clear_reward_dict = {
        '8': (lambda x: get_label( '{}{}'.format(MATERIAL_NAME_LABEL, x))),
        '20': (lambda x: get_label( '{}{}'.format(EVENT_RAID_ITEM_LABEL, x))),
        '23': (lambda x: 'Wyrmite'),
    }

    for i in range(1,QUEST_FIRST_CLEAR_COUNT+1):
        try:
            curr_row['FirstClearRewards'] = first_clear_dict[row['_FirstClearSetEntityType{}'.format(i)]]
        except KeyError:
            pass
    for i in range(1,QUEST_COMPLETE_COUNT+1):
        complete_type = row['_MissionCompleteType{}'.format(i)]
        complete_value = row['_MissionCompleteValues{}'.format(i)]
        clear_reward_type = row['_MissionsClearSetEntityType{}'.format(i)]

        try:
            curr_row['MissionCompleteType{}'.format(i)] = complete_type_dict[complete_type](complete_value)
            curr_row['MissionsClearSetEntityType{}'.format(i)] = clear_reward_dict[clear_reward_type](row['_MissionsClearSetEntityType{}'.format(i)])
            curr_row['MissionsClearSetEntityQuantity{}'.format(i)] = row['_MissionsClearSetEntityQuantity{}'.format(i)]
        except KeyError:
            pass

    first_clear1_type = row['_FirstClearSetEntityType1']
    try:
        curr_row['MissionCompleteEntityType'] = clear_reward_dict[
            first_clear1_type](row['_MissionCompleteEntityType'])
        curr_row['MissionCompleteEntityQuantity'] = row['_MissionCompleteEntityQuantity']
    except KeyError:
        pass

    existing_data[index] = (existing_row[0], curr_row)

def process_QuestBonusData(row, existing_data):

    found = False
    for index,existing_row in enumerate(existing_data):
        if existing_row[1]['_Gid'] == row['_Id']:
            found = True
            break
    if not found:
        return

    curr_row = existing_row[1]
    if row['_QuestBonusType'] == '1':
        curr_row['DailyDropQuantity'] = row['_QuestBonusCount']
        curr_row['DailyDropReward'] = ''
    elif row['_QuestBonusType'] == '2':
        curr_row['WeeklyDropQuantity'] = row['_QuestBonusCount']
        curr_row['WeeklyDropReward'] = ''

    existing_data[index] = (existing_row[0], curr_row)

def process_WeaponData(row, existing_data):
    new_row = OrderedDict()

    new_row['Id'] = row[ROW_INDEX]
    new_row['BaseId'] = row['_BaseId']
    new_row['FormId'] = row['_FormId']
    new_row['WeaponName'] = get_label(row['_Name'])
    new_row['WeaponNameJP'] = get_label(row['_Name'], lang='jp')
    new_row['Type'] = WEAPON_TYPE[int(row['_Type'])]
    new_row['Rarity'] = row['_Rarity']
    # Case when weapon has no elemental type
    try:
        new_row['ElementalType'] = ELEMENT_TYPE[int(row['_ElementalType'])]
    except IndexError:
        new_row['ElementalType'] = ''
    new_row['Obtain'] = '' # EDIT_THIS
    new_row['ReleaseDate'] = '' # EDIT_THIS
    new_row['Availability'] = '' # EDIT_THIS
    new_row['MinHp'] = row['_MinHp']
    new_row['MaxHp'] = row['_MaxHp']
    new_row['MinAtk'] = row['_MinAtk']
    new_row['MaxAtk'] = row['_MaxAtk']
    new_row['VariationId'] = 1
    # Case when weapon has no skill
    try:
        new_row['SkillName'] = get_label(SKILL_DATA_NAMES[row['_Skill']])
    except KeyError:
        new_row['SkillName'] = ''
    new_row['Abilities11'] = row['_Abilities11']
    new_row['Abilities21'] = row['_Abilities21']
    new_row['IsPlayable'] = 1
    new_row['FlavorText'] = get_label(row['_Text'])
    new_row['SellCoin'] = row['_SellCoin']
    new_row['SellDewPoint'] = row['_SellDewPoint']

    existing_data.append((new_row['WeaponName'], new_row))

def process_WeaponCraftData(row, existing_data):
    WEAPON_CRAFT_DATA_MATERIAL_COUNT = 5

    found = False
    for index,existing_row in enumerate(existing_data):
        if existing_row[1]['Id'] == row[ROW_INDEX]:
            found = True
            break
    assert(found)

    curr_row = existing_row[1]
    curr_row['FortCraftLevel'] = row['_FortCraftLevel']
    curr_row['AssembleCoin'] = row['_AssembleCoin']
    curr_row['DisassembleCoin'] = row['_DisassembleCoin']
    curr_row['MainWeaponId'] = row['_MainWeaponId']
    curr_row['MainWeaponQuantity'] = row['_MainWeaponQuantity']

    for i in range(1,WEAPON_CRAFT_DATA_MATERIAL_COUNT+1):
        curr_row['CraftMaterialType{}'.format(i)] = row['_CraftEntityType{}'.format(i)]
        curr_row['CraftMaterial{}'.format(i)] = get_label('{}{}'.format(MATERIAL_NAME_LABEL, row['_CraftEntityId{}'.format(i)]))
        curr_row['CraftMaterialQuantity{}'.format(i)] = row['_CraftEntityQuantity{}'.format(i)]
    existing_data[index] = (existing_row[0], curr_row)

def process_WeaponCraftTree(row, existing_data):
    found = False
    for index,existing_row in enumerate(existing_data):
        if existing_row[1]['Id'] == row['_CraftWeaponId']:
            found = True
            break
    assert(found)

    curr_row = existing_row[1]
    curr_row['CraftNodeId'] = row['_CraftNodeId']
    curr_row['ParentCraftNodeId'] = row['_ParentCraftNodeId']
    curr_row['CraftGroupId'] = row['_CraftGroupId']
    existing_data[index] = (existing_row[0], curr_row)

def build_wikitext_row(template_name, row, delim='|'):
    row_str = '{{' + template_name + delim
    if template_name in ORDERING_DATA:
        key_source = ORDERING_DATA[template_name]
    else:
        key_source = row.keys()
    row_str += delim.join(['{}={}'.format(k, row[k]) for k in key_source if k in row])
    if delim[0] == '\n':
        row_str += '\n'
    row_str += '}}'
    return row_str

def row_as_wikitext(row, template_name, display_name = None):
    text = ""
    if display_name:
        text += display_name
        text += ENTRY_LINE_BREAK
        text += build_wikitext_row(template_name, row, delim='\n|')
        text += ENTRY_LINE_BREAK
    else:
        text += build_wikitext_row(template_name, row)
        text += '\n'
    return text

def row_as_wikitable(row, template_name=None, display_name=None, delim=' || '):
    return '|-\n| {}\n'.format(delim.join([v for v in row.values()]))

def row_as_wikirow(row, template_name=None, display_name=None, delim='|'):
    return '{{' + template_name + '|' + delim.join(row) + '}}\n'

DATA_PARSER_PROCESSING = {
    'AbilityLimitedGroup': ('AbilityLimitedGroup', row_as_wikitext, process_AbilityLimitedGroup),
    'AbilityData': ('Ability', row_as_wikitext,
        [('AbilityShiftGroup', process_AbilityShiftGroup),
         ('AbilityData', process_AbilityData)]),
    'AmuletData': ('Wyrmprint', row_as_wikitext, process_AmuletData),
    'BuildEventItem': ('Material', row_as_wikitext, process_Material),
    'CharaData': ('Adventurer', row_as_wikitext, process_CharaData),
    'CollectEventItem': ('Material', row_as_wikitext, process_Material),
    'SkillData': ('Skill', row_as_wikitext, process_SkillData),
    'DragonData': ('Dragon', row_as_wikitext, process_Dragon),
    'ExAbilityData': ('CoAbility', row_as_wikitext, process_ExAbilityData),
    'EmblemData': ('Epithet', row_as_wikitable, process_EmblemData),
    'FortPlantData': ('Facility', row_as_wikitext,
        [('FortPlantDetail', process_FortPlantDetail),
         ('FortPlantData', process_FortPlantData)]),
    'MaterialData': ('Material', row_as_wikitext, process_Material),
    'RaidEventItem': ('Material', row_as_wikitext, process_Material),
    'MissionDailyData': ('EndeavorRow', row_as_wikirow, process_MissionData),
    'MissionPeriodData': ('EndeavorRow', row_as_wikirow, process_MissionData),
    'MissionNormalData': ('EndeavorRow', row_as_wikirow, process_MissionData),
    'QuestData': ('QuestDisplay', row_as_wikitext,
        [('QuestData', process_QuestData),
            ('QuestRewardData', process_QuestRewardData),
            ('QuestEvent', process_QuestBonusData),
        ]),
    'WeaponData': ('Weapon', row_as_wikitext,
        [('WeaponData', process_WeaponData),
            ('WeaponCraftTree', process_WeaponCraftTree),
            ('WeaponCraftData', process_WeaponCraftData)])
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process CSV data into Wikitext.')
    parser.add_argument('-i', type=str, help='directory of input text files', default='./')
    parser.add_argument('-o', type=str, help='directory of output text files  (default: ./data-output)', default='./data-output')
    parser.add_argument('-j', type=str, help='path to json file with ordering', default='')
    # parser.add_argument('-data', type=list)
    parser.add_argument('--delete_old', help='delete older output files', dest='delete_old', action='store_true')

    args = parser.parse_args()
    if args.delete_old:
        if os.path.exists(args.o):
            try:
                rmtree(args.o)
                print('Deleted old {}'.format(args.o))
            except Exception:
                print('Could not delete old {}'.format(args.o))
    if args.j:
        with open(args.j, 'r') as json_ordering_fp:
            ORDERING_DATA = json.load(json_ordering_fp)
    if not os.path.exists(args.o):
        os.makedirs(args.o)

    in_dir = args.i if args.i[-1] == '/' else args.i+'/'
    out_dir = args.o if args.o[-1] == '/' else args.o+'/'

    TEXT_LABEL_DICT['en'] = csv_as_index(in_dir+TEXT_LABEL+EXT, tabs=True)
    try:
        TEXT_LABEL_DICT['jp'] = csv_as_index(in_dir+TEXT_LABEL_JP+EXT, tabs=True)
    except:
        pass
    SKILL_DATA_NAMES = csv_as_index(in_dir+SKILL_DATA_NAME+EXT, value_key='_Name')

    # find_fmt_params(in_dir, out_dir)

    for data_name, process_params in DATA_PARSER_PROCESSING.items():
        template, formatter, process_info = process_params
        parser = DataParser(data_name, template, formatter, process_info)
        parser.process()
        parser.emit(out_dir)
        print('Saved {}{}'.format(data_name, EXT))

