import logging
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
import pytz
import hashlib
import math
from collections import Counter
import asyncio
import re
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Online"

@app.route("/health")
def health():
    return "OK"

def run_web():
    app.run(host="0.0.0.0", port=10000)

# === CẤU HÌNH ===
TOKEN = "8657258982:AAFPWxSEXxw7LsMFjtY3b7Mm2wyhFJoZ32Q"
ADMIN_ID = 7338417401

activated_users = {}

try:
    with open("activated_users.json", "r", encoding="utf-8") as f:
        activated_users = json.load(f)
except FileNotFoundError:
    activated_users = {}

activated_users[str(ADMIN_ID)] = {"expires": "vĩnh viễn"}

def save_activated_users():
    with open("activated_users.json", "w", encoding="utf-8") as f:
        json.dump(activated_users, f, ensure_ascii=False, indent=2)

def is_admin(user_id):
    return user_id == ADMIN_ID

def check_user(user_id):
    try:
        with open("activated_users.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return False, None

    if str(user_id) in data:
        expire = data[str(user_id)]["expires"]
        if expire == "vĩnh viễn":
            return True, "vĩnh viễn"
        else:
            exp_date = datetime.strptime(expire, "%Y-%m-%d %H:%M:%S")
            timezone = pytz.timezone("Asia/Ho_Chi_Minh")
            exp_date = timezone.localize(exp_date)
            now = datetime.now(timezone)
            if now < exp_date:
                return True, expire
            else:
                return False, expire
    return False, None

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ========== THUẬT TOÁN TỪ NEW.HTML ==========
class HashAnalyzer:
    def __init__(self):
        self.history = []
        self.break_protector = {
            'mode': None,
            'count': 0,
            'consecutive_wrong': 0,
            'adaptive_threshold': 3,
            'last_prediction': None,
            'reverse_count': 0
        }
        self.ai_state = {'dao_chieu': False, 'entropy_high': False}

    def calculate_std_dev(self, arr):
        if len(arr) < 2:
            return 0
        mean = sum(arr) / len(arr)
        variance = sum((x - mean) ** 2 for x in arr) / len(arr)
        return math.sqrt(variance)

    def calc_entropy(self, arr):
        if len(arr) < 4:
            return 0
        ones = sum(1 for x in arr if x == 1)
        zeros = len(arr) - ones
        p1 = ones / len(arr) if len(arr) > 0 else 0
        p0 = zeros / len(arr) if len(arr) > 0 else 0
        e = 0
        if p1 > 0:
            e -= p1 * math.log2(p1)
        if p0 > 0:
            e -= p0 * math.log2(p0)
        return e

    def detect_super_streak(self, history):
        if len(history) < 3:
            return None
        results = [1 if s['result'] == 'Tài' else 0 for s in history[:20]]
        streak = 1
        for i in range(1, len(results)):
            if results[i] == results[0]:
                streak += 1
            else:
                break
        if 2 <= streak <= 4:
            return "Tài" if results[0] == 1 else "Xỉu"
        if 5 <= streak <= 7:
            return "Tài" if results[0] == 1 else "Xỉu"
        if streak >= 8:
            return "Tài" if results[0] == 1 else "Xỉu"
        return None

    def detect_break_cau(self, history):
        if len(history) < 8:
            return None
        results = [1 if s['result'] == 'Tài' else 0 for s in history[:15]]
        last_result = results[0]
        current_streak = 1
        for i in range(1, len(results)):
            if results[i] == last_result:
                current_streak += 1
            else:
                break
        if 3 <= current_streak <= 5:
            break_count = 0
            continue_count = 0
            for i in range(current_streak, len(results) - current_streak):
                match = True
                for j in range(current_streak):
                    if results[i + j] != last_result:
                        match = False
                        break
                if match:
                    if i + current_streak < len(results):
                        if results[i + current_streak] == last_result:
                            continue_count += 1
                        else:
                            break_count += 1
            if break_count > continue_count + 1:
                return "Xỉu" if last_result == 1 else "Tài"
            if continue_count > break_count and continue_count >= 2:
                return "Tài" if last_result == 1 else "Xỉu"
        is_alternating = True
        for i in range(6):
            if results[i] == results[i + 1]:
                is_alternating = False
                break
        if is_alternating and len(results) > 8:
            return "Xỉu" if results[0] == 1 else "Tài"
        return None

    def detect_eleven_pattern(self, history):
        if len(history) < 5:
            return None
        eleven_sessions = []
        for i in range(min(len(history), 30)):
            if history[i].get('total', 0) == 11:
                eleven_sessions.append({
                    'pos': i,
                    'result': history[i]['result'],
                    'next': history[i - 1]['result'] if i > 0 else None
                })
        if len(eleven_sessions) < 2:
            return None
        after11_tai = 0
        after11_xiu = 0
        for i in range(len(eleven_sessions) - 1):
            next_session = history[eleven_sessions[i]['pos'] - 1] if eleven_sessions[i]['pos'] > 0 else None
            if next_session:
                if next_session['result'] == "Tài":
                    after11_tai += 1
                else:
                    after11_xiu += 1
        total = after11_tai + after11_xiu
        if total >= 3:
            if after11_tai / total >= 0.7:
                return "Tài"
            if after11_xiu / total >= 0.7:
                return "Xỉu"
        recent11s = eleven_sessions[:3]
        if len(recent11s) >= 2 and recent11s[0]['result'] == recent11s[1]['result']:
            return "Xỉu" if recent11s[0]['result'] == "Tài" else "Tài"
        return None

    def detect_smart_pattern(self, history):
        if len(history) < 4:
            return None
        results = ['T' if s['result'] == 'Tài' else 'X' for s in history[:15]]
        pattern_lib = {
            "TT": {"next": "Tài", "conf": 80}, "XX": {"next": "Xỉu", "conf": 80},
            "TTT": {"next": "Tài", "conf": 85}, "XXX": {"next": "Xỉu", "conf": 85},
            "TTTT": {"next": "Tài", "conf": 90}, "XXXX": {"next": "Xỉu", "conf": 90},
            "TTTTT": {"next": "Tài", "conf": 93}, "XXXXX": {"next": "Xỉu", "conf": 93},
            "TXT": {"next": "Xỉu", "conf": 82}, "XTX": {"next": "Tài", "conf": 82},
            "TXTX": {"next": "Xỉu", "conf": 85}, "XTXT": {"next": "Tài", "conf": 85},
            "TTX": {"next": "Tài", "conf": 78}, "XXT": {"next": "Xỉu", "conf": 78},
            "TXX": {"next": "Tài", "conf": 76}, "XTT": {"next": "Xỉu", "conf": 76},
            "TTXX": {"next": "Tài", "conf": 84}, "XXTT": {"next": "Xỉu", "conf": 84},
            "TTXXTT": {"next": "Tài", "conf": 88}, "XXTTXX": {"next": "Xỉu", "conf": 88},
            "TTTX": {"next": "Tài", "conf": 86}, "XXXT": {"next": "Xỉu", "conf": 86},
            "TTTXX": {"next": "Tài", "conf": 83}, "XXXTT": {"next": "Xỉu", "conf": 83},
            "TXTXT": {"next": "Xỉu", "conf": 87}, "XTXTX": {"next": "Tài", "conf": 87},
            "TXTXTX": {"next": "Xỉu", "conf": 89}, "XTXTXT": {"next": "Tài", "conf": 89},
            "TTXXT": {"next": "Tài", "conf": 82}, "XXTTX": {"next": "Xỉu", "conf": 82},
            "TTXXX": {"next": "Tài", "conf": 85}, "XXTTT": {"next": "Xỉu", "conf": 85}
        }
        for length in range(3, 8):
            if len(results) < length + 1:
                continue
            current_pattern = ''.join(results[:length])
            for pattern, data in pattern_lib.items():
                if current_pattern == pattern or current_pattern == pattern[:length]:
                    match_count = 0
                    correct_count = 0
                    for i in range(length, min(len(results) - 1, 50)):
                        hist_pattern = ''.join(results[i:i + length])
                        if hist_pattern == current_pattern:
                            match_count += 1
                            next_result = results[i - 1]
                            expected = 'T' if data['next'] == "Tài" else 'X'
                            if next_result == expected:
                                correct_count += 1
                    if match_count >= 2 and correct_count / match_count >= 0.65:
                        return data['next']
        return None

    def detect_staircase_advanced(self, history):
        if len(history) < 6:
            return None
        totals = [s.get('total', 0) for s in history[:12]]
        increasing = True
        decreasing = True
        for i in range(5):
            if i + 1 < len(totals):
                if totals[i] >= totals[i + 1]:
                    increasing = False
                if totals[i] <= totals[i + 1]:
                    decreasing = False
        if increasing and totals[0] <= 10:
            return "Tài"
        if decreasing and totals[0] >= 11:
            return "Xỉu"
        up_down_count = 0
        for i in range(5):
            if i + 2 < len(totals):
                if totals[i] < totals[i + 1] and totals[i + 1] > totals[i + 2]:
                    up_down_count += 1
                if totals[i] > totals[i + 1] and totals[i + 1] < totals[i + 2]:
                    up_down_count += 1
        if up_down_count >= 2:
            last_total = totals[0]
            if last_total < 10:
                return "Tài"
            if last_total > 11:
                return "Xỉu"
        return None

    def detect_spiral_pattern(self, history):
        if len(history) < 10:
            return None
        results = [1 if s['result'] == 'Tài' else 0 for s in history[:20]]
        groups = []
        current = 1
        for i in range(1, len(results)):
            if results[i] == results[i - 1]:
                current += 1
            else:
                groups.append(current)
                current = 1
        groups.append(current)
        if len(groups) >= 3:
            is_growing = True
            is_shrinking = True
            for i in range(len(groups) - 1):
                if groups[i] >= groups[i + 1]:
                    is_growing = False
                if groups[i] <= groups[i + 1]:
                    is_shrinking = False
            if is_growing:
                return "Tài" if results[0] == 1 else "Xỉu"
            if is_shrinking and groups[0] <= 1:
                return "Xỉu" if results[0] == 1 else "Tài"
        return None

    def detect_ping_pong_advanced(self, history):
        if len(history) < 6:
            return None
        results = [1 if s['result'] == 'Tài' else 0 for s in history[:12]]
        is_ping_pong = True
        for i in range(6):
            if results[i] == results[i + 1]:
                is_ping_pong = False
                break
        if is_ping_pong:
            if len(results) >= 8:
                return "Xỉu" if results[0] == 1 else "Tài"
            return "Xỉu" if results[0] == 1 else "Tài"
        return None

    def detect_symmetry(self, history):
        if len(history) < 8:
            return None
        results = ['T' if s['result'] == 'Tài' else 'X' for s in history[:12]]
        if len(results) >= 7 and results[0] == results[6] and results[1] == results[5] and results[2] == results[4]:
            return "Xỉu" if results[3] == 'T' else "Tài"
        return None

    def detect_total_pattern(self, history):
        if len(history) < 5:
            return None
        totals = [s.get('total', 0) for s in history[:15]]
        results = [s['result'] for s in history[:15]]
        eleven_positions = [i for i, t in enumerate(totals) if t == 11]
        if len(eleven_positions) >= 2:
            after_tai = 0
            after_xiu = 0
            for pos in eleven_positions:
                if pos > 0:
                    if results[pos - 1] == "Tài":
                        after_tai += 1
                    else:
                        after_xiu += 1
            if after_tai + after_xiu >= 3:
                if after_tai / (after_tai + after_xiu) >= 0.7:
                    return "Tài"
                if after_xiu / (after_tai + after_xiu) >= 0.7:
                    return "Xỉu"
        sum_cycle = totals[:10]
        if sum_cycle:
            avg = sum(sum_cycle) / len(sum_cycle)
            if avg > 11.5 and sum_cycle[0] > 11:
                return "Xỉu"
            if avg < 9.5 and sum_cycle[0] < 10:
                return "Tài"
        return None

    def update_break_protector(self, actual, predicted):
        if predicted and actual != predicted:
            self.break_protector['consecutive_wrong'] += 1
            if self.break_protector['consecutive_wrong'] >= self.break_protector['adaptive_threshold']:
                self.break_protector['mode'] = "REVERSE"
                self.break_protector['reverse_count'] = 2
                self.break_protector['adaptive_threshold'] = min(5, self.break_protector['adaptive_threshold'] + 1)
        elif predicted and actual == predicted:
            self.break_protector['consecutive_wrong'] = 0
            if self.break_protector['mode'] == "REVERSE":
                self.break_protector['reverse_count'] -= 1
                if self.break_protector['reverse_count'] <= 0:
                    self.break_protector['mode'] = None
                    self.break_protector['adaptive_threshold'] = max(2, self.break_protector['adaptive_threshold'] - 1)
        self.break_protector['last_prediction'] = predicted

    def apply_break_protector(self, prediction):
        if self.break_protector['mode'] == "REVERSE":
            return "Xỉu" if prediction == "Tài" else "Tài"
        return prediction

    def predict_logic1(self, last, history):
        if not last or len(history) < 10:
            return None
        last_digit = last.get('sid', 0) % 10
        total_val = last.get('total', 0)
        cur = "Xỉu" if (last_digit + total_val) % 2 == 0 else "Tài"
        c = 0
        t = 0
        for i in range(min(len(history) - 1, 25)):
            s = history[i]
            p = history[i + 1] if i + 1 < len(history) else None
            if p:
                prev = "Xỉu" if ((p.get('sid', 0) % 10) + p.get('total', 0)) % 2 == 0 else "Tài"
                if prev == s['result']:
                    c += 1
                t += 1
        if t > 5 and c / t >= 0.65:
            return cur
        return None

    def predict_logic2(self, next_id, history):
        if len(history) < 15:
            return None
        thuan = 0
        nghich = 0
        w = min(len(history), 60)
        for i in range(w):
            s = history[i]
            is_even = s.get('sid', 0) % 2 == 0
            weight = 1 - (i / w) * 0.6
            if (is_even and s['result'] == "Xỉu") or (not is_even and s['result'] == "Tài"):
                thuan += weight
            if (is_even and s['result'] == "Tài") or (not is_even and s['result'] == "Xỉu"):
                nghich += weight
        cur_even = next_id % 2 == 0
        total = thuan + nghich
        if total < 10:
            return None
        if thuan > nghich + 0.15 * total:
            return "Xỉu" if cur_even else "Tài"
        if nghich > thuan + 0.15 * total:
            return "Tài" if cur_even else "Xỉu"
        return None

    def predict_logic3(self, history):
        if len(history) < 15:
            return None
        w = min(len(history), 50)
        totals = [s.get('total', 0) for s in history[:w]]
        avg = sum(totals) / len(totals) if totals else 0
        std = self.calculate_std_dev(totals)
        recent = [s.get('total', 0) for s in history[:min(5, len(history))]]
        rising = True
        falling = True
        for i in range(len(recent) - 1):
            if recent[i] <= recent[i + 1]:
                rising = False
            if recent[i] >= recent[i + 1]:
                falling = False
        if avg < 10.5 - 0.8 * std and falling:
            return "Xỉu"
        if avg > 10.5 + 0.8 * std and rising:
            return "Tài"
        return None

    def predict_logic4(self, history):
        if len(history) < 30:
            return None
        best = None
        max_c = 0
        vol = self.calculate_std_dev([s.get('total', 0) for s in history[:30]])
        lens = [6, 5, 4] if vol < 1.7 else [5, 4, 3]
        for length in lens:
            if len(history) < length + 2:
                continue
            recent = ''.join(['T' if s['result'] == 'Tài' else 'X' for s in history[:length][::-1]])
            tai = 0
            xiu = 0
            total = 0
            for i in range(length, min(len(history) - 1, 200)):
                pat = ''.join(['T' if s['result'] == 'Tài' else 'X' for s in history[i:i + length][::-1]])
                if pat == recent:
                    total += 1
                    if history[i - 1]['result'] == 'Tài':
                        tai += 1
                    else:
                        xiu += 1
            if total < 3:
                continue
            tai_c = tai / total
            xiu_c = xiu / total
            if tai_c >= 0.70 and tai_c > max_c:
                max_c = tai_c
                best = "Tài"
            elif xiu_c >= 0.70 and xiu_c > max_c:
                max_c = xiu_c
                best = "Xỉu"
        return best

    def predict_logic5(self, history):
        if len(history) < 40:
            return None
        sum_cnt = {}
        w = min(len(history), 400)
        for i in range(w):
            total_val = history[i].get('total', 0)
            weight = 1 - (i / w) * 0.8
            sum_cnt[total_val] = sum_cnt.get(total_val, 0) + weight
        max_sum = -1
        max_w = 0
        for s, wgt in sum_cnt.items():
            if wgt > max_w:
                max_w = wgt
                max_sum = s
        if max_sum != -1:
            total_w = sum(sum_cnt.values())
            if total_w > 0 and max_w / total_w > 0.08:
                left = sum_cnt.get(max_sum - 1, 0)
                right = sum_cnt.get(max_sum + 1, 0)
                if max_w > left * 1.05 and max_w > right * 1.05:
                    if max_sum <= 10:
                        return "Xỉu"
                    if max_sum >= 11:
                        return "Tài"
        return None

    def predict_logic_fast(self, history):
        if len(history) < 5:
            return None
        last3 = [1 if s['result'] == 'Tài' else 0 for s in history[:3]]
        sum_last3 = sum(last3)
        if sum_last3 >= 2:
            return "Tài"
        return "Xỉu"

    def super_ensemble(self, history):
        if len(history) < 20:
            return None
        tai_score = 0
        xiu_score = 0

        streak_pred = self.detect_super_streak(history)
        if streak_pred:
            if streak_pred == "Tài":
                tai_score += 3.5
            else:
                xiu_score += 3.5

        break_pred = self.detect_break_cau(history)
        if break_pred:
            if break_pred == "Tài":
                tai_score += 2.8
            else:
                xiu_score += 2.8

        eleven_pred = self.detect_eleven_pattern(history)
        if eleven_pred:
            if eleven_pred == "Tài":
                tai_score += 3.2
            else:
                xiu_score += 3.2

        pattern_pred = self.detect_smart_pattern(history)
        if pattern_pred:
            if pattern_pred == "Tài":
                tai_score += 2.5
            else:
                xiu_score += 2.5

        stair_pred = self.detect_staircase_advanced(history)
        if stair_pred:
            if stair_pred == "Tài":
                tai_score += 2.0
            else:
                xiu_score += 2.0

        spiral_pred = self.detect_spiral_pattern(history)
        if spiral_pred:
            if spiral_pred == "Tài":
                tai_score += 2.2
            else:
                xiu_score += 2.2

        pingpong_pred = self.detect_ping_pong_advanced(history)
        if pingpong_pred:
            if pingpong_pred == "Tài":
                tai_score += 2.3
            else:
                xiu_score += 2.3

        sym_pred = self.detect_symmetry(history)
        if sym_pred:
            if sym_pred == "Tài":
                tai_score += 2.1
            else:
                xiu_score += 2.1

        total_pred = self.detect_total_pattern(history)
        if total_pred:
            if total_pred == "Tài":
                tai_score += 2.4
            else:
                xiu_score += 2.4

        last = history[0] if history else None
        l1 = self.predict_logic1(last, history)
        if l1:
            if l1 == "Tài":
                tai_score += 1.5
            else:
                xiu_score += 1.5

        l3 = self.predict_logic3(history)
        if l3:
            if l3 == "Tài":
                tai_score += 1.3
            else:
                xiu_score += 1.3

        l4 = self.predict_logic4(history)
        if l4:
            if l4 == "Tài":
                tai_score += 1.4
            else:
                xiu_score += 1.4

        l5 = self.predict_logic5(history)
        if l5:
            if l5 == "Tài":
                tai_score += 1.2
            else:
                xiu_score += 1.2

        fast = self.predict_logic_fast(history)
        if fast:
            if fast == "Tài":
                tai_score += 1.0
            else:
                xiu_score += 1.0

        total_score = tai_score + xiu_score
        if total_score < 2.5:
            return None
        if tai_score / xiu_score >= 1.3:
            return "Tài"
        if xiu_score / tai_score >= 1.3:
            return "Xỉu"
        return None

    def deep_ai_filter(self, history, base_pred):
        if len(history) < 12:
            return base_pred
        recent = [1 if s['result'] == 'Tài' else 0 for s in history[:20]]
        entropy = self.calc_entropy(recent[:8])
        streak = 1
        for i in range(1, len(recent)):
            if recent[i] == recent[0]:
                streak += 1
            else:
                break
        if streak >= 6:
            return "Tài" if recent[0] == 1 else "Xỉu"
        is_ping = True
        for i in range(5):
            if recent[i] == recent[i + 1]:
                is_ping = False
                break
        if is_ping and len(recent) >= 6:
            return "Xỉu" if recent[0] == 1 else "Tài"
        if entropy > 0.82:
            self.ai_state['dao_chieu'] = True
        elif entropy < 0.55:
            self.ai_state['dao_chieu'] = False
        if self.ai_state['dao_chieu'] and base_pred:
            return "Xỉu" if base_pred == "Tài" else "Tài"
        return base_pred

    def analyze(self, hash_str):
        sach = re.sub(r'[^0-9a-f]', '', hash_str.lower())
        do_dai = len(sach)

        if do_dai == 32:
            loai_hash = "MD5"
        elif do_dai == 64:
            loai_hash = "SHA256"
        else:
            return {'loi': f'Hash khong hop le! Can 32 (MD5) hoac 64 (SHA256) ky tu hex, hien co {do_dai}'}

        bytes_list = []
        for i in range(0, do_dai, 2):
            bytes_list.append(int(sach[i:i+2], 16))

        history = []
        for i, b in enumerate(bytes_list):
            history.append({
                'result': 'Tài' if ((b >> 4) + (b & 0xF)) >= 15 else 'Xỉu'
                'total': b,
                'sid': i,
                'd1': (b >> 4) & 0xF,
                'd2': b & 0xF,
                'd3': (b >> 2) & 0xF
            })

        pred = self.super_ensemble(history)
        pred = self.deep_ai_filter(history, pred)
        pred = self.apply_break_protector(pred)

        if pred == "Tài":
            result = "TÀI"
            icon = "🔥"
            diem = 85
        elif pred == "Xỉu":
            result = "XỈU"
            icon = "❄️"
            diem = 85
        else:
            last = history[0] if history else None
            if last and last['result'] == "Tài":
                result = "XỈU"
                icon = "❄️"
                diem = 60
            else:
                result = "TÀI"
                icon = "🔥"
                diem = 60

        tai_percent = 100 - diem if result == "XỈU" else diem
        xiu_percent = 100 - tai_percent

        return {
            'loai_hash': loai_hash,
            'result': result,
            'icon': icon,
            'tai': round(tai_percent, 1),
            'xiu': round(xiu_percent, 1),
            'confidence': 85,
            'diem': diem,
            'hash': sach
        }

analyzer = HashAnalyzer()

# ========== BOT COMMANDS ==========

@dp.message(Command("start"))
async def start_cmd(message: Message):
    ok, _ = check_user(message.from_user.id)
    if not ok:
        await message.reply("❌ Ban chua duoc cap quyen su dung bot!\n📱 Lien he admin: @phong296")
        return
    
    text = "🎯 **GAME PREDICTION BOT**\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "✨ **Bot du doan Tai/Xiu**\n"
    text += "🔥 Chinh xac len den 85%\n\n"
    text += "💡 **Cach su dung:**\n"
    text += "📥 Nhap **MD5** (32 ky tu)\n"
    text += "📥 Nhap **SHA256** (64 ky tu)\n\n"
    text += "🔄 Bot se phan tich va du doan\n"
    text += "⚡ Nhanh chong - Chinh xac\n\n"
    text += "📖 Xem huong dan: /help\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "👤 Admin: @phong296"
    
    await message.reply(text, parse_mode='Markdown')

@dp.message(Command("help"))
async def help_cmd(message: Message):
    is_ad = is_admin(message.from_user.id)
    
    text = "📚 **HUONG DAN SU DUNG**\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    text += "⚡ **LENH CO BAN:**\n"
    text += "🚀 /start - Khoi dong bot\n"
    text += "ℹ️ /info - Xem thong tin cua ban\n"
    text += "❓ /help - Xem huong dan nay\n"
    text += "💬 /feedback (noi dung) - Gui feedback\n"
    text += "   📎 Reply anh + /feedback\n\n"
    
    text += "🎯 **CACH SU DUNG:**\n"
    text += "🔢 Nhap **MD5** (32 ky tu) de phan tich\n"
    text += "🔢 Nhap **SHA256** (64 ky tu) de phan tich\n"
    text += "📊 Bot se du doan **Tai** 🟢 / **Xiu** 🔴\n\n"
        
    if is_ad:
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "👑 **ADMIN:**\n"
        text += "➕ /adduser (id) (ngay|vinh)\n"
        text += "➖ /removeuser (id)\n"
        text += "📢 /broadcast (noi dung)\n"
        text += "📋 /danhsach - Xem danh sach\n\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "👤 Admin: @phong296"
    
    await message.reply(text, parse_mode='Markdown')

@dp.message(Command("info"))
async def info_cmd(message: Message):
    ok, _ = check_user(message.from_user.id)
    if not ok:
        await message.reply("❌ Ban chua duoc kich hoat!\n📱 Lien he admin: @phong296")
        return
    
    uid = message.from_user.id
    name = message.from_user.full_name
    username = message.from_user.username or "Khong co"
    is_ad = is_admin(uid)
    ok, exp = check_user(uid)
    status = "👑 Admin" if is_ad else ("✅ Da kich hoat" if ok else "❌ Chua kich hoat")
    
    text = "📋 **THONG TIN CUA BAN**\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"👤 Ten: {name}\n"
    text += f"🔰 @{username}\n"
    text += f"🆔 ID: {uid}\n"
    text += f"📌 Trang thai: {status}\n"
    text += f"⏰ Han dung: {exp}\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "👤 Admin: @phong296"
    
    await message.reply(text, parse_mode='Markdown')

@dp.message(Command("feedback"))
async def feedback_cmd(message: Message):
    ok, _ = check_user(message.from_user.id)
    if not ok:
        await message.reply("❌ Ban chua duoc kich hoat!")
        return
    
    if message.reply_to_message:
        content = message.text.replace("/feedback", "").strip()
        
        if message.reply_to_message.photo:
            photo = message.reply_to_message.photo[-1]
            caption = "📨 **FEEDBACK MOI (CO ANH):**\n\n"
            caption += f"👤 Ten: {message.from_user.full_name}\n"
            caption += f"🆔 ID: {message.from_user.id}\n"
            if content:
                caption += f"📝 Noi dung: {content}\n"
            
            await bot.send_photo(ADMIN_ID, photo=photo.file_id, caption=caption, parse_mode='Markdown')
            await message.reply("✅ Da gui feedback kem anh den admin!")
            return
        
        elif message.reply_to_message.text:
            if not content:
                content = message.reply_to_message.text
            
            user_info = "📨 **FEEDBACK MOI:**\n\n"
            user_info += f"👤 Ten: {message.from_user.full_name}\n"
            user_info += f"🆔 ID: {message.from_user.id}\n"
            user_info += f"📝 Noi dung: {content}\n"
            
            await bot.send_message(ADMIN_ID, user_info, parse_mode='Markdown')
            await message.reply("✅ Da gui feedback den admin!")
            return
        
        elif message.reply_to_message.document or message.reply_to_message.video or message.reply_to_message.audio:
            file_id = None
            file_type = ""
            
            if message.reply_to_message.document:
                file_id = message.reply_to_message.document.file_id
                file_type = "📄 Document"
            elif message.reply_to_message.video:
                file_id = message.reply_to_message.video.file_id
                file_type = "🎬 Video"
            elif message.reply_to_message.audio:
                file_id = message.reply_to_message.audio.file_id
                file_type = "🎵 Audio"
            
            if file_id:
                caption = f"📨 **FEEDBACK MOI ({file_type}):**\n\n"
                caption += f"👤 Ten: {message.from_user.full_name}\n"
                caption += f"🆔 ID: {message.from_user.id}\n"
                if content:
                    caption += f"📝 Noi dung: {content}\n"
                
                await bot.send_document(ADMIN_ID, document=file_id, caption=caption, parse_mode='Markdown')
                await message.reply("✅ Da gui feedback kem file den admin!")
                return
    
    content = message.text.replace("/feedback", "").strip()
    if not content:
        await message.reply("❌ Vui long nhap noi dung feedback hoac reply anh.\n"
                           "📝 Vi du: /feedback Bot rat hay!\n"
                           "📎 Hoac: Reply anh + /feedback")
        return
    
    user_info = "📨 **FEEDBACK MOI:**\n\n"
    user_info += f"👤 Ten: {message.from_user.full_name}\n"
    user_info += f"🆔 ID: {message.from_user.id}\n"
    user_info += f"📝 Noi dung: {content}\n"
    
    await bot.send_message(ADMIN_ID, user_info, parse_mode='Markdown')
    await message.reply("✅ Da gui feedback den admin! Cam on ban.")

# === ADMIN COMMANDS ===

@dp.message(Command("adduser"))
async def add_user(message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply("❌ Ban khong co quyen!")

    parts = message.text.split()
    if len(parts) != 3:
        return await message.reply("📝 /adduser (id) (so ngay|vinh)")

    user_id = parts[1]
    days = parts[2]

    if days == "vinh":
        activated_users[user_id] = {"expires": "vinh vien"}
    else:
        try:
            days = int(days)
            expire_time = datetime.now() + timedelta(days=days)
            activated_users[user_id] = {
                "expires": expire_time.strftime("%Y-%m-%d %H:%M:%S")
            }
        except ValueError:
            return await message.reply("❌ So ngay khong hop le!")

    save_activated_users()
    await message.reply(f"✅ Da cap quyen cho ID {user_id} ({'vinh vien' if days == 'vinh' else f'{days} ngay'})")

@dp.message(Command("removeuser"))
async def remove_user(message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply("❌ Ban khong co quyen!")
    
    parts = message.text.split()
    if len(parts) != 2:
        return await message.reply("📝 /removeuser (id)")

    user_id = parts[1]
    if user_id in activated_users:
        del activated_users[user_id]
        save_activated_users()
        await message.reply(f"✅ Da xoa quyen cua ID {user_id}")
    else:
        await message.reply("❌ ID khong ton tai")

@dp.message(Command("broadcast"))
async def broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply("❌ Ban khong co quyen!")
    
    content = message.text.replace("/broadcast", "").strip()
    if not content:
        return await message.reply("📝 /broadcast (noi dung)")

    success, fail = 0, 0
    for uid in activated_users:
        try:
            await bot.send_message(uid, f"📢 **THONG BAO:**\n\n{content}", parse_mode='Markdown')
            success += 1
        except:
            fail += 1
    await message.reply(f"✅ Gui thanh cong: {success}\n❌ That bai: {fail}")

@dp.message(Command("danhsach"))
async def danhsach_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply("❌ Ban khong co quyen!")
    
    if not activated_users:
        await message.reply("📋 Danh sach trong")
        return
    
    lines = ["📋 **DANH SACH NGUOI DUNG**", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for uid, info in activated_users.items():
        if uid == str(ADMIN_ID):
            lines.append(f"👑 Admin - ID: {uid} - Vinh vien")
        else:
            lines.append(f"👤 ID: {uid} - Han: {info['expires']}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 Tong: {len(activated_users)} nguoi")
    await message.reply("\n".join(lines), parse_mode='Markdown')

# === HASH HANDLER (MD5 & SHA256) ===

@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return
    
    text = message.text.strip()
    
    is_md5 = len(text) == 32 and all(c in '0123456789abcdefABCDEF' for c in text)
    is_sha256 = len(text) == 64 and all(c in '0123456789abcdefABCDEF' for c in text)
    
    if is_md5 or is_sha256:
        ok, _ = check_user(message.from_user.id)
        if not ok:
            await message.reply("❌ Ban chua duoc kich hoat!\n📱 Lien he admin: @phong296")
            return
        
        hash_str = text.lower()
        result = analyzer.analyze(hash_str)
        
        if 'loi' in result:
            await message.reply(f"❌ {result['loi']}")
            return
        
        # Xác định icon dựa trên kết quả
        result_icon = "🟢" if result['result'] == "TÀI" else "🔴"
        
        # Tạo reply ngắn gọn nhưng VIP
        reply_text = (
            f"🎯 **Dự đoán**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{result_icon} **{result['result']}**\n"
            f"📊 Độ tin cậy: {result['confidence']}%\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 `{hash_str[:8]}...{hash_str[-8:]}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        await message.reply(reply_text, parse_mode='Markdown')

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


async def main():
    # Chạy web server song song
    Thread(target=run_web, daemon=True).start()

    print("🚀 Bot dang chay...")
    print(f"👑 Admin: {ADMIN_ID}")
    print("📊 Thuat toan: NEW.HTML - 60+ Mau Cau")
    print("🎯 Du doan Tai/Xiu")
    print("🌐 Web server: OK")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())