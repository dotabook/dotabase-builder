# Generates json files from the database.db
# these files serve 2 purposes:
# 1. gives the viewer an idea of what is in the database
# 2. provides a way to look at what changes between each update
from __main__ import session
from dotabase import *
from collections import OrderedDict
import os
import json
import shutil
import re

json_path = os.path.join(dotabase_dir, "../json/")

def write_json(filename, data):
	text = json.dumps(data, indent="\t")
	with open(filename, "w+") as f:
		f.write(text) # Do it like this so it doesnt break mid-file


# dumps an sqlalchemy table to json
def dump_table(table, query=None):
	full_data = []
	if query is None:
		query = session.query(table)
	for item in query:
		data = OrderedDict()
		for col in table.__table__.columns:
			value = getattr(item, col.name)
			if col.name in [ "json_data", "ability_special" ]:
				data[col.name] = json.loads(value, object_pairs_hook=OrderedDict)
			elif value is None or value == "":
				continue
			elif isinstance(value, int) or isinstance(value, bool) or isinstance(value, float):
				data[col.name] = value
			else:
				data[col.name] = str(value)
		full_data.append(data)
	return full_data

def dump_heroes(filename):
	data = dump_table(Hero)
	write_json(filename, data)

def dump_abilities(filename):
	data = dump_table(Ability)
	write_json(filename, data)

def dump_items(filename):
	data = dump_table(Item)
	write_json(filename, data)

def dump_emoticons(filename):
	data = dump_table(Emoticon)
	write_json(filename, data)

def dump_chatwheel(filename):
	data = dump_table(ChatWheelMessage)
	write_json(filename, data)

def dump_criteria(filename):
	data = dump_table(Criterion)
	write_json(filename, data)

def dump_voices(filename):
	data = dump_table(Voice)
	write_json(filename, data)

def dump_loadingscreens(filename):
	data = dump_table(LoadingScreen)
	write_json(filename, data)

def dump_talents(filename):
	data = dump_table(Talent)
	write_json(filename, data)

def dump_responses(directory):
	os.makedirs(directory)
	for voice in session.query(Voice):
		data = dump_table(Response, voice.responses)
		filename = voice.name.lower().replace(" ", "_")
		filename = re.sub(r"[^a-z_]", "", filename)
		filename = os.path.join(directory, f"{filename}.json")
		write_json(filename, data)


def generate_json():
	print("generating json files...")
	if os.path.exists(json_path):
		shutil.rmtree(json_path)
	os.makedirs(json_path)
	dump_heroes(json_path + "heroes.json")
	dump_items(json_path + "items.json")
	dump_abilities(json_path + "abilities.json")
	dump_emoticons(json_path + "emoticons.json")
	dump_chatwheel(json_path + "chatwheel.json")
	dump_criteria(json_path + "criteria.json")
	dump_voices(json_path + "voices.json")
	dump_loadingscreens(json_path + "loadingscreens.json")
	dump_talents(json_path + "talents.json")
	dump_responses(json_path + "responses")