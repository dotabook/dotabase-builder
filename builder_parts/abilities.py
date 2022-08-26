from builder import session
from dotabase import *
from utils import *
from valve2json import DotaFiles, DotaPaths
import re

def build_replacements_dict(ability: Ability, scepter=False, shard=False):
	specials = json.loads(ability.ability_special, object_pairs_hook=OrderedDict)
	result = {
		"abilityduration": ability.duration,
		"abilitychanneltime": ability.channel_time,
		"abilitycastpoint": ability.cast_point,
		"abilitycastrange": ability.cast_range,
		"abilitychargerestoretime": ability.cooldown,
		"charge_restore_time": ability.cooldown,
		"abilitycooldown": ability.cooldown,
		"max_charges": ability.charges,
		"AbilityCharges": ability.charges,
		"abilitymanacost": ability.mana_cost
	}
	for attrib in specials:
		is_scepter_upgrade = attrib.get("scepter_upgrade") == "1" and not ability.scepter_grants
		if is_scepter_upgrade and not scepter:
			continue
		is_shard_upgrade = attrib.get("shard_upgrade") == "1" and not ability.shard_grants
		if is_shard_upgrade and not shard:
			continue
		if (attrib["key"] not in result) or is_scepter_upgrade or is_shard_upgrade:
			value = attrib.get("value")
			if shard and attrib.get("shard_value"):
				value = attrib.get("shard_value")
			if scepter and attrib.get("scepter_value"):
				value = attrib.get("scepter_value")
			if value and value != "":
				result[attrib["key"]] = value
		if shard and attrib.get("shard_bonus"):
			result[f"bonus_{attrib['key']}"] = attrib.get("shard_bonus")
			result[f"shard_{attrib['key']}"] = attrib.get("shard_value")
		if scepter and attrib.get("scepter_bonus"):
			result[f"bonus_{attrib['key']}"] = attrib.get("scepter_bonus")
			result[f"scepter_{attrib['key']}"] = attrib.get("scepter_value")
	return result

def load():
	session.query(Ability).delete()
	print("Abilities")

	added_ids = []

	print("- loading abilities from ability scripts")
	# load all of the ability scripts data information
	data = DotaFiles.npc_abilities.read()["DOTAAbilities"]
	for abilityname in data:
		if(abilityname == "Version" or
			abilityname == "ability_deward" or
			abilityname == "dota_base_ability" or
			not data[abilityname]['ID'].isdigit()):
			continue

		ability_data = data[abilityname]
		ability = Ability()

		def get_val(key, default_base=False):
			if key in ability_data:
				val = ability_data[key]
				if ' ' in val and all(x == val.split(' ')[0] for x in val.split(' ')):
					return val.split(' ')[0]
				return val
			elif "AbilityValues" in ability_data and key in ability_data["AbilityValues"]:
				val = ability_data["AbilityValues"][key]
				if not isinstance(val, str):
					val = val["value"]
				if ' ' in val and all(x == val.split(' ')[0] for x in val.split(' ')):
					return val.split(' ')[0]
				return val
			elif default_base:
				return data["ability_base"][key]
			else:
				return None

		ability.name = abilityname
		ability.id = int(ability_data['ID'])
		ability.type = get_val('AbilityType', default_base=True)
		ability.behavior = get_val('AbilityBehavior', default_base=True)
		ability.cast_range = clean_values(get_val('AbilityCastRange'))
		ability.cast_point = clean_values(get_val('AbilityCastPoint'))
		ability.channel_time = clean_values(get_val('AbilityChannelTime'))
		ability.charges = clean_values(get_val('AbilityCharges'))
		if ability.charges:
			ability.cooldown = clean_values(get_val('AbilityChargeRestoreTime'))
		else:
			ability.cooldown = clean_values(get_val('AbilityCooldown'))
		ability.duration = clean_values(get_val('AbilityDuration'))
		ability.damage = clean_values(get_val('AbilityDamage'))
		ability.mana_cost = clean_values(get_val('AbilityManaCost'))
		ability.ability_special = json.dumps(get_ability_special(ability_data, abilityname), indent=4)
		ability.scepter_grants = get_val("IsGrantedByScepter") == "1"
		ability.shard_grants = get_val("IsGrantedByShard") == "1"
		ability.scepter_upgrades = get_val("HasScepterUpgrade") == "1"
		ability.shard_upgrades = get_val("HasShardUpgrade") == "1"


		if ability.id in added_ids:
			printerr(f"duplicate id on: {abilityname}")
			continue
		added_ids.append(ability.id)

		def get_enum_val(key, prefix):
			value = get_val(key)
			if value:
				return re.sub(prefix, "", value).lower().replace(" ", "")
			else:
				return value

		ability.behavior = get_enum_val('AbilityBehavior', "DOTA_ABILITY_BEHAVIOR_")
		ability.damage_type = get_enum_val('AbilityUnitDamageType', "DAMAGE_TYPE_")
		ability.spell_immunity = get_enum_val('SpellImmunityType', "SPELL_IMMUNITY_(ENEMIES|ALLIES)_")
		ability.target_team = get_enum_val('AbilityUnitTargetTeam', "DOTA_UNIT_TARGET_TEAM_")
		ability.dispellable = get_enum_val('SpellDispellableType', "SPELL_DISPELLABLE_")


		ability.json_data = json.dumps(ability_data, indent=4)

		session.add(ability)

	print("- intermediate ability linking")
	# intermedate re-linking and setting of ability metadata
	for ability in session.query(Ability):
		ability_data = json.loads(ability.json_data, object_pairs_hook=OrderedDict)
		abilityvalues = ability_data.get("AbilityValues")
		if abilityvalues:
			for key, valdict in abilityvalues.items():
				if not isinstance(valdict, str):
					for subkey in valdict:
						if subkey.startswith("special_bonus"):
							# this is a talent value we need to link
							value = valdict[subkey]
							value = re.sub(r"(\+|-)", "", value) # clean it up so we dont have duplicate things (the header contains these)
							talent = session.query(Ability).filter_by(name=subkey).first()
							if talent is None:
								if subkey not in [ "special_bonus_scepter", "special_bonus_shard" ]:
									printerr(f"Can't find special_bonus when attempting to link '{ability.name}' '{key}' ('{subkey}')")
								break
							talent_ability_special = json.loads(talent.ability_special, object_pairs_hook=OrderedDict)
							talent_ability_special.append({
								"key": f"bonus_{key}",
								"value": value
							})
							talent.ability_special = json.dumps(talent_ability_special, indent=4)


	print("- loading ability data from dota_english")
	# Load additional information from the dota_english.txt file
	data = DotaFiles.abilities_english.read()["lang"]["Tokens"]
	data = CaseInsensitiveDict(data)
	for ability in session.query(Ability):
		ability_tooltip = "DOTA_Tooltip_ability_" + ability.name 
		ability.localized_name = data.get(ability_tooltip, ability.name)
		ability.description = data.get(ability_tooltip + "_Description", "")
		ability.lore = data.get(ability_tooltip + "_Lore", "")
		if ability.scepter_upgrades:
			ability.scepter_description = data.get(ability_tooltip + "_scepter_description", "")
		else:
			ability.scepter_description = ""
		if ability.shard_upgrades:
			ability.shard_description = data.get(ability_tooltip + "_shard_description", "")
		else:
			ability.shard_description = ""

		notes = []
		for i in range(8):
			key = f"{ability_tooltip}_Note{i}"
			if key in data:
				notes.append(data[key])
		ability.note = "" if len(notes) == 0 else "\n".join(notes)

		ability_special_value_fixes = {
			"abilityduration": ability.duration
		}

		ability_special = json.loads(ability.ability_special, object_pairs_hook=OrderedDict)
		ability_special = ability_special_add_talent(ability_special, session.query(Ability), ability.name)
		ability_special = ability_special_add_header(ability_special, data, ability.name)
		for key in ability_special_value_fixes:
			for special in ability_special:
				if special["key"] == key and special["value"] == "":
					special["value"] = ability_special_value_fixes[key]
		ability.ability_special = json.dumps(ability_special, indent=4)

		is_probably_talent = ability.name.startswith("special_bonus")
		replacements_dict = build_replacements_dict(ability)
		ability.localized_name = clean_description(ability.localized_name, replacements_dict, value_bolding=False, report_errors=not is_probably_talent)
		ability.description = clean_description(ability.description, replacements_dict, report_errors=not is_probably_talent)
		ability.note = clean_description(ability.note, replacements_dict)
		replacements_dict = build_replacements_dict(ability, scepter=True)
		ability.scepter_description = clean_description(ability.scepter_description, replacements_dict)
		replacements_dict = build_replacements_dict(ability, shard=True)
		ability.shard_description = clean_description(ability.shard_description, replacements_dict)

		if ability.localized_name.startswith(": "):
			ability.localized_name = ability.localized_name[2:]

		if ability.scepter_grants and ability.scepter_description == "":
			ability.scepter_description = f"Adds new ability: {ability.localized_name}."

		if ability.shard_grants and ability.shard_description == "":
			ability.shard_description = f"Adds new ability: {ability.localized_name}."

		# special case for skywrath who has an innate shard
		if ability.id == 5584:
			ability.shard_description = data.get("DOTA_Tooltip_ability_skywrath_mage_shard_description", "")

	print("- adding ability icon files")
	# Add img files to ability
	for ability in session.query(Ability):
		iconpath = DotaPaths.ability_icon_images + ability.name + "_png.png"
		if os.path.isfile(config.vpk_path + iconpath):
			ability.icon = iconpath
		else:
			ability.icon = DotaPaths.ability_icon_images + "attribute_bonus_png.png"

	session.commit()