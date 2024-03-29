
from django.db.models import F, Q, When, Case, Value, TextField, Max, Window, Subquery, OuterRef
from django.db.models import Count
from django.db.models.functions import Coalesce, Lead, RowNumber
from django.http import JsonResponse, HttpResponse
from datetime import datetime
from django.template.defaultfilters import floatformat

from app.models import *
import psycopg2

# Create your views here
from dbs_zadanie.settings import env


def message(request):
    SECRET_KEY = env('SECRET_KEY')
    conn = psycopg2.connect(
        host=env('DATABASE_HOST'),
        port=env('DATABASE_PORT'),
        database=env('DATABASE_NAME'),
        user=env('DATABASE_USER'),
        password=env('DATABASE_PASS')
    )

    cur = conn.cursor()
    poziadavka = {}
    cur.execute("SELECT VERSION();")
    poziadavka["prva"] = cur.fetchone()[0]
    cur.execute("SELECT pg_database_size('dota2')/1024/1024 as dota2_db_size;")
    poziadavka["druha"] = str(cur.fetchone()[0])

    conn.commit()
    cur.close()
    conn.close()
    odpoved = JsonResponse(poziadavka)
    return odpoved


def prvy_endpoint(request):
    SECRET_KEY = env('SECRET_KEY')
    conn = psycopg2.connect(
        host=env('DATABASE_HOST'),
        port=env('DATABASE_PORT'),
        database=env('DATABASE_NAME'),
        user=env('DATABASE_USER'),
        password=env('DATABASE_PASS')
    )
    cur = conn.cursor()

    query = "WITH temp AS( SELECT name, CAST(EXTRACT(epoch from release_date) AS INT) AS patch_start_date, CAST(EXTRACT(epoch from LEAD(release_date,1) OVER(ORDER BY release_date ASC)) AS INT) AS patch_end_date FROM patches) SELECT patches.name as patch_version, patches.patch_start_date, patches.patch_end_date,  matches.id as match_id, CAST(ROUND(matches.duration/60.0,2) as FLOAT) as match_duration FROM temp patches LEFT JOIN matches ON matches.start_time > patches.patch_start_date AND matches.start_time <  patches.patch_end_date"
    cur.execute(query)
    output = cur.fetchall()
    patches = []

    for i in output:
        if len(patches) != 0 and i[0] == patches[-1]["patch_version"]:
            patches[-1]["matches"].append({"match_id": i[3], "duration": i[4]})
        else:
            patch = {}
            patch["patch_version"] = i[0]
            patch["patch_start_date"] = i[1]
            patch["patch_end_date"] = i[2]
            if i[3] is not None:
                patch["matches"] = [{"match_id": i[3], "duration": i[4]}]
            else:
                patch["matches"] = []
            patches.append(patch)

    vypisanie = {"patches": patches}
    return JsonResponse(vypisanie)


def druhy_endpoint(request, id):
    SECRET_KEY = env('SECRET_KEY')
    conn = psycopg2.connect(
        host=env('DATABASE_HOST'),
        port=env('DATABASE_PORT'),
        database=env('DATABASE_NAME'),
        user=env('DATABASE_USER'),
        password=env('DATABASE_PASS')
    )
    cur = conn.cursor()

    query = "SELECT players.id, COALESCE(players.nick, 'unknown') as player_nick, heroes.localized_name as hero_localized_name, CAST(ROUND(matches.duration/60.0,2) as FLOAT) as match_duration_minutes, COALESCE(matches_players_details.xp_hero,0) + COALESCE(matches_players_details.xp_creep,0) +  COALESCE(matches_players_details.xp_other,0) + COALESCE(matches_players_details.xp_roshan,0) as experiences_gained, matches_players_details.level as level_gained, matches.id as match_id, (CASE WHEN matches_players_details.player_slot <= 4 THEN matches.radiant_win WHEN matches_players_details.player_slot >= 128 THEN not matches.radiant_win END) as winner from players JOIN matches_players_details ON players.id = matches_players_details.player_id JOIN heroes ON matches_players_details.hero_id=heroes.id JOIN matches ON matches_players_details.match_id=matches.id where players.id =" + id + " ORDER BY match_id"
    cur.execute(query)
    output = cur.fetchall()
    vypisanie = {"id": output[0][0], "player_nick": output[0][1], "matches": []}

    for i in output:
        match = {}
        match["match_id"] = i[6]
        match["hero_localized_name"] = i[2]
        match["match_duration_minutes"] = i[3]
        match["experiences_gained"] = i[4]
        match["level_gained"] = i[5]
        match["winner"] = i[7]
        vypisanie["matches"].append(match)
    return JsonResponse(vypisanie)


def treti_endpoint(request, id):
    SECRET_KEY = env('SECRET_KEY')
    conn = psycopg2.connect(
        host=env('DATABASE_HOST'),
        port=env('DATABASE_PORT'),
        database=env('DATABASE_NAME'),
        user=env('DATABASE_USER'),
        password=env('DATABASE_PASS')
    )
    cur = conn.cursor()

    query = "SELECT players.id, COALESCE(players.nick, 'unknown') as player_nick, heroes.localized_name as hero_localized_name, matches.id as match_id, COALESCE(game_objectives.subtype, 'NO_ACTION') as hero_action, COUNT(*) FROM players JOIN matches_players_details ON  players.id = matches_players_details.player_id JOIN heroes ON matches_players_details.hero_id=heroes.id JOIN matches ON matches_players_details.match_id=matches.id FULL OUTER JOIN game_objectives  ON matches_players_details.id = game_objectives.match_player_detail_id_1 where players.id = " + id + " GROUP BY players.id, heroes.localized_name, matches.id, game_objectives.subtype ORDER BY match_id"
    cur.execute(query)
    output = cur.fetchall()
    vypisanie = {"id": output[0][0], "player_nick": output[0][1], "matches": []}

    match = {}
    for i in output:
        if len(match) != 0 and i[3] != match["match_id"]:
            vypisanie["matches"].append(match)
            match = {}
        if match == {}:
            match["match_id"] = i[3]
            match["hero_localized_name"] = i[2]
            match["actions"] = []
        if match != {}:
            match["actions"].append({"hero_action": i[4], "count": i[5]})
    vypisanie["matches"].append(match)

    return JsonResponse(vypisanie)


def stvrty_endpoint(request, id):
    SECRET_KEY = env('SECRET_KEY')
    conn = psycopg2.connect(
        host=env('DATABASE_HOST'),
        port=env('DATABASE_PORT'),
        database=env('DATABASE_NAME'),
        user=env('DATABASE_USER'),
        password=env('DATABASE_PASS')
    )
    cur = conn.cursor()

    query = "WITH tab AS( SELECT ability_name, hero_name, bucket, winner, COUNT(bucket) as bucket_count from (SELECT abilities.name as ability_name, ability_upgrades.time as upgrade_time, heroes.localized_name as hero_name, ROUND(ability_upgrades.time/(matches.duration/100.0)) as when, (CASE WHEN ROUND(ability_upgrades.time/(matches.duration/100.0)) <= 9 THEN '0-9' WHEN ROUND(ability_upgrades.time/(matches.duration/100.0)) >=10 AND ROUND(ability_upgrades.time/(matches.duration/100.0)) <20 THEN '10-19' WHEN ROUND(ability_upgrades.time/(matches.duration/100.0)) >=20 AND ROUND(ability_upgrades.time/(matches.duration/100.0)) <30 THEN '20-29' WHEN ROUND(ability_upgrades.time/(matches.duration/100.0)) >=30 AND ROUND(ability_upgrades.time/(matches.duration/100.0)) <40 THEN '30-39' WHEN ROUND(ability_upgrades.time/(matches.duration/100.0)) >=40 AND ROUND(ability_upgrades.time/(matches.duration/100.0)) <50 THEN '40-49' WHEN ROUND(ability_upgrades.time/(matches.duration/100.0)) >=50 AND ROUND(ability_upgrades.time/(matches.duration/100.0)) <60 THEN '50-59' WHEN ROUND(ability_upgrades.time/(matches.duration/100.0)) >=60 AND ROUND(ability_upgrades.time/(matches.duration/100.0)) <70 THEN '60-69' WHEN ROUND(ability_upgrades.time/(matches.duration/100.0)) >=70 AND ROUND(ability_upgrades.time/(matches.duration/100.0)) <80 THEN '70-79' WHEN ROUND(ability_upgrades.time/(matches.duration/100.0)) >=80 AND ROUND(ability_upgrades.time/(matches.duration/100.0)) <90 THEN '80-89' WHEN ROUND(ability_upgrades.time/(matches.duration/100.0)) >=90 AND ROUND(ability_upgrades.time/(matches.duration/100.0)) <100 THEN '90-99' WHEN ROUND(ability_upgrades.time/(matches.duration/100.0)) >=100 THEN '100-109'  END) as bucket, (CASE  WHEN matches_players_details.player_slot <= 4 THEN matches.radiant_win  WHEN matches_players_details.player_slot >= 128 THEN not matches.radiant_win  END) as winner from abilities JOIN ability_upgrades ON ability_upgrades.ability_id = abilities.id JOIN matches_players_details ON matches_players_details.id = ability_upgrades.match_player_detail_id JOIN heroes ON heroes.id = matches_players_details.hero_id JOIN matches ON matches.id = matches_players_details.match_id WHERE abilities.id =" + id + " ORDER BY bucket ) AS t1 GROUP by t1.ability_name, t1.hero_name, t1.winner, t1.bucket ORDER BY bucket, winner) SELECT * from(SELECT tab.ability_name, tab.hero_name, tab.bucket, tab.winner, tab.bucket_count, row_number() over (partition by winner, hero_name order by tab.bucket_count desc) as rank from tab) ranks where rank <=1 ORDER BY hero_name, bucket"
    cur.execute(query)
    output = cur.fetchall()
    vypisanie = {"id": output[0][0], "player_nick": output[0][1], "matches": []}

    match = {}
    for i in output:
        if len(match) != 0 and i[3] != match["match_id"]:
            vypisanie["matches"].append(match)
            match = {}
        if match == {}:
            match["match_id"] = i[3]
            match["hero_localized_name"] = i[2]
            match["abilities"] = []
        if match != {}:
            match["abilities"].append({"ability_name": i[4], "count": i[5], "upgrade_level": i[6]})
    vypisanie["matches"].append(match)
    return JsonResponse(vypisanie)


def z5_prvy_endpoint(request, id):
    SECRET_KEY = env('SECRET_KEY')
    conn = psycopg2.connect(
        host=env('DATABASE_HOST'),
        port=env('DATABASE_PORT'),
        database=env('DATABASE_NAME'),
        user=env('DATABASE_USER'),
        password=env('DATABASE_PASS')
    )
    cur = conn.cursor()

    query = "WITH t AS (SELECT matches.id as match_id,  heroes.id as hero_id, heroes.localized_name as hero_name, items.id as item_id, items.name as item_name, COUNT(items) as count, (CASE WHEN matches_players_details.player_slot <= 4 THEN matches.radiant_win  WHEN matches_players_details.player_slot >= 128 THEN not matches.radiant_win END) as winner from matches JOIN matches_players_details ON matches.id = matches_players_details.match_id JOIN heroes ON matches_players_details.hero_id = heroes.id JOIN purchase_logs ON matches_players_details.id = purchase_logs.match_player_detail_id JOIN items ON purchase_logs.item_id = items.id where matches.id = " + id + " GROUP BY matches.id, heroes.localized_name, items.name, heroes.id, items.id, matches_players_details.player_slot ORDER BY heroes.localized_name, items.name) select * from(select match_id, hero_id, hero_name, item_id,item_name, count, winner, row_number() over  (partition by hero_name order by count desc,item_name) as rank from t) ranks where rank <=5 AND winner = true ORDER BY hero_id, rank"
    cur.execute(query)
    output = cur.fetchall()
    vypisanie = {"id": output[0][0], "heroes": []}

    hero = {}
    for i in output:
        if len(hero) != 0 and i[1] != hero["id"]:
            vypisanie["heroes"].append(hero)
            hero = {}
        if hero == {}:
            hero["id"] = i[1]
            hero["name"] = i[2]
            hero["top_purchases"] = []
        if hero != {}:
            hero["top_purchases"].append({"id": i[3], "name": i[4], "count": i[5]})
    vypisanie["heroes"].append(hero)
    return JsonResponse(vypisanie)


def z5_druhy_endpoint(request, id):
    SECRET_KEY = env('SECRET_KEY')
    conn = psycopg2.connect(
        host=env('DATABASE_HOST'),
        port=env('DATABASE_PORT'),
        database=env('DATABASE_NAME'),
        user=env('DATABASE_USER'),
        password=env('DATABASE_PASS')
    )
    cur = conn.cursor()

    query = "WITH tab AS( SELECT ability_id, ability_name, hero_id, hero_name, bucket, winner, COUNT(bucket) as bucket_count from (SELECT abilities.id as ability_id, abilities.name as ability_name, ability_upgrades.time as upgrade_time, heroes.id as hero_id, heroes.localized_name as hero_name, (CASE WHEN (ability_upgrades.time*100.0/matches.duration) <= 9 THEN '0-9' WHEN (ability_upgrades.time*100.0/matches.duration) >=10 AND (ability_upgrades.time*100.0/matches.duration) <20 THEN '10-19' WHEN (ability_upgrades.time*100.0/matches.duration) >=20 AND (ability_upgrades.time*100.0/matches.duration) <30 THEN '20-29' WHEN (ability_upgrades.time*100.0/matches.duration) >=30 AND (ability_upgrades.time*100.0/matches.duration) <40 THEN '30-39' WHEN (ability_upgrades.time*100.0/matches.duration) >=40 AND (ability_upgrades.time*100.0/matches.duration) <50 THEN '40-49' WHEN (ability_upgrades.time*100.0/matches.duration) >=50 AND (ability_upgrades.time*100.0/matches.duration) <60 THEN '50-59' WHEN (ability_upgrades.time*100.0/matches.duration) >=60 AND (ability_upgrades.time*100.0/matches.duration) <70 THEN '60-69' WHEN (ability_upgrades.time*100.0/matches.duration) >=70 AND (ability_upgrades.time*100.0/matches.duration) <80 THEN '70-79' WHEN (ability_upgrades.time*100.0/matches.duration) >=80 AND (ability_upgrades.time*100.0/matches.duration) <90 THEN '80-89' WHEN (ability_upgrades.time*100.0/matches.duration) >=90 AND (ability_upgrades.time*100.0/matches.duration) <100 THEN '90-99' WHEN (ability_upgrades.time*100.0/matches.duration) >=100 THEN '100-109' END) as bucket, (CASE WHEN matches_players_details.player_slot <= 4 THEN matches.radiant_win WHEN matches_players_details.player_slot >= 128 THEN not matches.radiant_win END) as winner from abilities JOIN ability_upgrades ON ability_upgrades.ability_id = abilities.id JOIN matches_players_details ON matches_players_details.id = ability_upgrades.match_player_detail_id JOIN heroes ON heroes.id = matches_players_details.hero_id JOIN matches ON matches.id = matches_players_details.match_id WHERE abilities.id = " + id + " ORDER BY bucket) AS t1 GROUP by t1.ability_name, t1. ability_id, t1.hero_name, t1.hero_id, t1.winner, t1.bucket ORDER BY bucket, winner ) SELECT * from(SELECT tab.ability_id, tab.ability_name, tab.hero_id, tab.hero_name, tab.bucket, tab.winner, tab.bucket_count, row_number() over (partition by winner, hero_name order by tab.bucket_count desc) as rank from tab) ranks where rank <=1 ORDER BY hero_id, winner"
    cur.execute(query)
    output = cur.fetchall()
    vypisanie = {"id": output[0][0], "name": output[0][1], "heroes": []}

    hero = {}
    for i in output:
        if len(hero) != 0 and i[2] != hero["id"]:
            vypisanie["heroes"].append(hero)
            hero = {}
        if hero == {}:
            hero["id"] = i[2]
            hero["name"] = i[3]
        if hero != {}:
            if i[5] is True:
                hero["usage_winners"] = {"bucket": i[4], "count": i[6]}
            else:
                hero["usage_loosers"] = {"bucket": i[4], "count": i[6]}
    vypisanie["heroes"].append(hero)

    return JsonResponse(vypisanie)


def z5_treti_endpoint(request):
    SECRET_KEY = env('SECRET_KEY')
    conn = psycopg2.connect(
        host=env('DATABASE_HOST'),
        port=env('DATABASE_PORT'),
        database=env('DATABASE_NAME'),
        user=env('DATABASE_USER'),
        password=env('DATABASE_PASS')
    )
    cur = conn.cursor()

    query = "WITH t AS (SELECT matches_players_details.match_id as match_id, localized_name as hero_name, heroes.id as hero_id, game_objectives.id as objective_id from heroes JOIN matches_players_details ON matches_players_details.hero_id = heroes.id JOIN game_objectives ON game_objectives.match_player_detail_id_1 = matches_players_details.id WHERE game_objectives.subtype = 'CHAT_MESSAGE_TOWER_KILL') SELECT * FROM( Select DISTINCT ON (hero_name) hero_id,hero_name, count(1) from (Select match_id, hero_name, objective_id, hero_id, row_number() over (order by objective_id) as rn, row_number() over (partition by hero_name, match_id order by objective_id) as part_rn From t) as table2 Group by hero_name, match_id, hero_id, (rn-part_rn) ORDER BY hero_name, count DESC) as table3 ORDER BY count DESC, hero_name ASC"
    cur.execute(query)
    output = cur.fetchall()
    vypisanie = {"heroes": []}

    for i in output:
        hero = {"id": i[0], "name": i[1], "tower_kills": i[2]}
        vypisanie["heroes"].append(hero)

    return JsonResponse(vypisanie)


def z6_1(request):
    patches = Patches.objects.using("dota")\
        .values("name","release_date")\
        .annotate(
            end = Window(expression=Lead('release_date'))
        )


    return HttpResponse(patches, content_type='application/json')


def z6_2(request, url_id):
    player = MatchesPlayersDetails.objects.using("dota").filter(player_id=url_id).select_related("hero", "player", "match"). \
        values("player_id", "match_id","hero__localized_name","level") \
        .annotate(
            winner = Case(
                When(Q(player_slot__lte=4), then = "match__radiant_win"),
                When(Q(player_slot__gte=128) & Q(match__radiant_win=True), then = False),
                When(Q(player_slot__gte=128) & Q(match__radiant_win=False), then = True)
            )
        )\
        .annotate(
            playe_nick = Coalesce('player__nick', Value('unknown'), output_field=TextField()),
        )\
        .annotate(
            match_duration = F("match__duration")/60.0
    )\
        .annotate(
            hero_xp=Coalesce('xp_hero', Value(0)),
            creep_xp=Coalesce('xp_creep', Value(0)),
            other_xp=Coalesce('xp_other', Value(0)),
            roshan_xp=Coalesce('xp_roshan', Value(0)),
            experiences_gained=F("hero_xp") + F("creep_xp") + F("other_xp") + F("roshan_xp")
        )\


    row0 =  player[0]
    vypisanie = {"id": list(row0.values())[0], "player_nick": list(row0.values())[5], "matches": []}

    for i in player:
        match = {}
        match["match_id"] = list(i.values())[1]
        match["hero_localized_name"] = list(i.values())[2]
        match["match_duration_minutes"] = round((list(i.values())[6]),2)
        match["experiences_gained"] = list(i.values())[11]
        match["level_gained"] = list(i.values())[3]
        match["winner"] = list(i.values())[4]
        vypisanie["matches"].append(match)

    return JsonResponse(vypisanie)


def z6_3(request, url_id):
    player = MatchesPlayersDetails.objects.using("dota").select_related("hero", "player")\
        .prefetch_related("match_player_detail_id_1").filter(player=url_id)\
        .values("player__id", "hero__localized_name", "match_id")\
        .annotate(
            playe_nick=Coalesce('player__nick', Value('unknown'), output_field=TextField()),
        )\
        .annotate(
            hero_action=Coalesce('match_player_detail_id_1__subtype', Value('NO_ACTION'), output_field=TextField())
        )\
        .order_by('match_id')\
        .annotate(
            count = Count('hero_action')
        )\


    row0 =  player[0]
    vypisanie = {"id": list(row0.values())[0], "player_nick": list(row0.values())[3], "matches": []}

    match = {}
    for i in player:
        if len(match) != 0 and list(i.values())[2] != match["match_id"]:
            vypisanie["matches"].append(match)
            match = {}
        if match == {}:
            match["match_id"] = list(i.values())[2]
            match["hero_localized_name"] = list(i.values())[1]
            match["actions"] = []
        if match != {}:
            match["actions"].append({"hero_action": list(i.values())[4], "count": list(i.values())[5]})
    vypisanie["matches"].append(match)

    return JsonResponse(vypisanie)


def z6_4(request, url_id):
    player = MatchesPlayersDetails.objects.using("dota").select_related("abilityupgrades","ability")\
        .filter(player=url_id)\
        .values("player__id", "hero__localized_name", "match_id", "abilityupgrades__ability__name")\
        .annotate(
            playe_nick=Coalesce('player__nick', Value('unknown'), output_field=TextField()),
        )\
        .order_by('match_id')\
        .annotate(
            count=Count('abilityupgrades__ability__name')
        )\
        .annotate(
            level = Max('abilityupgrades__level')
         ) \


    row0 = player[0]
    vypisanie = {"id": list(row0.values())[0], "player_nick": list(row0.values())[4], "matches": []}

    match = {}
    for i in player:
        if len(match) != 0 and list(i.values())[2] != match["match_id"]:
            vypisanie["matches"].append(match)
            match = {}
        if match == {}:
            match["match_id"] = list(i.values())[2]
            match["hero_localized_name"] = list(i.values())[1]
            match["abilities"] = []
        if match != {}:
            match["abilities"].append({"ability_name": list(i.values())[3], "count": list(i.values())[5], "upgrade_level": list(i.values())[6]})
    vypisanie["matches"].append(match)

    return JsonResponse(vypisanie)


def z6_5(request, url_id):
    purchaces = MatchesPlayersDetails.objects.using("dota").filter(match_id=url_id).select_related("hero", "match","purchaselogs"). \
        values("match_id","purchaselogs__item_id", "hero__id", "hero__localized_name", "purchaselogs__item_id__name") \
        .annotate(
            winner = Case(
                When(Q(player_slot__lte=4), then = "match__radiant_win"),
                When(Q(player_slot__gte=128) & Q(match__radiant_win=True), then = False),
                When(Q(player_slot__gte=128) & Q(match__radiant_win=False), then = True)
            )
        )\
        .filter(winner = True)\
        .order_by('hero__id', 'purchaselogs__item_id__name')\
        .annotate(
            count = Count("purchaselogs__item_id__name")
        )\
        .order_by('hero__localized_name', F('count').desc())\

    row0 = purchaces[0]
    vypisanie = {"id": list(row0.values())[0], "heroes": []}

    count = 0
    hero = {}
    for i in purchaces:
        if len(hero) != 0 and list(i.values())[2] != hero["id"]:
            vypisanie["heroes"].append(hero)
            hero = {}
            count = 0
        if hero == {}:
            hero["id"] = list(i.values())[2]
            hero["name"] = list(i.values())[3]
            hero["top_purchases"] = []
        if hero != {} and count<5:
            hero["top_purchases"].append({"id": list(i.values())[1], "name": list(i.values())[4], "count": list(i.values())[6]})
            count += 1
   
    vypisanie["heroes"].append(hero)


    return JsonResponse(vypisanie)




def z6_6(reqest, url_id):
    abilities = AbilityUpgrades.objects.using("dota").filter(ability_id=url_id)\
        .select_related("ability", "match_player_detail", "match", "hero")\
        .values("match_player_detail__hero__id", "match_player_detail__hero__localized_name","ability__name") \
        .annotate(
            winner = Case(
                When(Q(match_player_detail__player_slot__gte=4), then = "match_player_detail__match__radiant_win"),
                When(Q(match_player_detail__player_slot__gte=128) & Q(match_player_detail__match__radiant_win=True), then = False),
                When(Q(match_player_detail__player_slot__gte=128) & Q(match_player_detail__match__radiant_win=False), then = True)
            )
        )\
        .annotate(
            ability_upgrade=F("time") * 100.0 / F("match_player_detail__match__duration"),
            bucket = Case(
                When(Q(ability_upgrade__lte=9), then = Value("0-9")),
                When(Q(ability_upgrade__gte=10) & Q(ability_upgrade__lt=20), then=Value("10-29")),
                When(Q(ability_upgrade__gte=20) & Q(ability_upgrade__lt=30), then=Value("20-29")),
                When(Q(ability_upgrade__gte=30) & Q(ability_upgrade__lt=40), then=Value("30-39")),
                When(Q(ability_upgrade__gte=40) & Q(ability_upgrade__lt=50), then=Value("40-49")),
                When(Q(ability_upgrade__gte=50) & Q(ability_upgrade__lt=60), then=Value("50-59")),
                When(Q(ability_upgrade__gte=60) & Q(ability_upgrade__lt=70), then=Value("60-69")),
                When(Q(ability_upgrade__gte=70) & Q(ability_upgrade__lt=80), then=Value("70-79")),
                When(Q(ability_upgrade__gte=80) & Q(ability_upgrade__lt=90), then=Value("80-89")),
                When(Q(ability_upgrade__gte=90) & Q(ability_upgrade__lt=100), then=Value("90-99")),
                When(Q(ability_upgrade__gte=100), then=Value("100-109"))
            )
        ) \


    top_abilities = abilities.filter(ability_id=url_id)\
        .values("match_player_detail__hero__id", "match_player_detail__hero__localized_name","ability__name","bucket") \
        .annotate(
            count = Count("bucket")
        )\
        .order_by("bucket")



    return HttpResponse(top_abilities, content_type='application/json')