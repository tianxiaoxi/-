#!/usr/bin/env python3
"""
extract_stats.py - L0 代码预处理（真人主播版）
从 reports/ 下所有 *_六维分析报告.md 中提取六维度评分、路径信号、心之壁等结构化数据，
输出 l0_raw.json 和 l0_stats.json。

与虚拟主播版的主要差异：
- 内容类型分类（IRL/聊天/游戏/音乐/舞蹈/美妆/美食/健身/户外/知识/带货/综合）
- 组织属性分类（MCN签约·大型/MCN签约·中小型/平台签约/独立/明星转型）
- 从业状态（活跃/瓶颈/停播淡出）
- 新增真人主播特有字段：外貌管理压力、私生活曝光风险
"""

import json
import re
import os
import math
import sys
from pathlib import Path
from collections import defaultdict, Counter

# Fix Windows console encoding for CJK filenames
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"

# ============================================================
# 1. Parsing Utilities
# ============================================================

def extract_section(text: str, heading_pattern: str) -> str | None:
    """Extract content between a heading and the next heading of same or higher level."""
    lines = text.split('\n')
    match_line = None
    heading_level = 0
    for i, line in enumerate(lines):
        m = re.match(r'^(#{1,6})\s+.*' + re.escape(heading_pattern) + r'.*', line)
        if m:
            match_line = i
            heading_level = len(m.group(1))
            break
    if match_line is None:
        return None

    end_line = len(lines)
    for i in range(match_line + 1, len(lines)):
        m = re.match(r'^(#{1,6})\s+', lines[i])
        if m and len(m.group(1)) <= heading_level:
            end_line = i
            break
    return '\n'.join(lines[match_line:end_line])


def parse_markdown_table(text: str) -> list[dict]:
    """Parse a markdown table into list of dicts with header keys."""
    lines = text.strip().split('\n')
    headers = None
    result = []
    for line in lines:
        line = line.strip()
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.split('|')]
        if cells and cells[0] == '':
            cells = cells[1:]
        if cells and cells[-1] == '':
            cells = cells[:-1]
        if not cells:
            continue
        if all(re.match(r'^[-:]+$', c) for c in cells if c):
            continue
        if headers is None:
            headers = cells
        else:
            row = {}
            for j, h in enumerate(headers):
                if j < len(cells):
                    row[h] = cells[j]
                else:
                    row[h] = ''
            result.append(row)
    return result


def strip_markdown_bold(text: str) -> str:
    """Remove ** bold markers from text."""
    return re.sub(r'\*\*', '', text).strip()


def parse_score(score_str: str) -> int | None:
    """Parse a score string like '9/10', '9', '**9/10**', 'N/A' into int or None."""
    s = strip_markdown_bold(score_str).strip()
    if s.upper() in ('N/A', '不适用', '—', '-', ''):
        return None
    m = re.match(r'(\d+)\s*/\s*10', s)
    if m:
        return int(m.group(1))
    m = re.match(r'(\d+)', s)
    if m:
        val = int(m.group(1))
        if 1 <= val <= 10:
            return val
    return None


def parse_signal_strength(s: str) -> str:
    """Normalize signal strength values."""
    s = strip_markdown_bold(s).strip()
    mapping = {
        '强': '强', '強い': '强',
        '中': '中', '中等': '中',
        '弱': '弱', '弱い': '弱',
        '沉默': '沉默', '无': '沉默',
        '不足': '不足', '情報不足': '不足', '信息不足': '不足',
        '不適用': '不适用', '不适用': '不适用',
        'N/A': '不适用', 'n/a': '不适用',
    }
    for k, v in mapping.items():
        if k.lower() in s.lower():
            return v
    if any(w in s for w in ['强', 'strong', 'high']):
        return '强'
    if any(w in s for w in ['中', 'medium', 'moderate']):
        return '中'
    if any(w in s for w in ['弱', 'weak', 'low']):
        return '弱'
    if any(w in s for w in ['沉默', 'silent', '无', 'none', '不适用', 'N/A']):
        return '沉默'
    if any(w in s for w in ['不足', 'insufficient', '未知']):
        return '不足'
    return s


# ============================================================
# 2. Report Parsers
# ============================================================

def parse_basic_info(text: str) -> dict:
    """Extract basic info from the 基本信息 section."""
    info = {}
    section = extract_section(text, '基本信息')
    if section:
        rows = parse_markdown_table(section)
        for row in rows:
            key = row.get('项目', row.get('属性', row.get('**项目**', '')))
            key = strip_markdown_bold(key)
            val = row.get('内容', row.get('**内容**', ''))
            val = strip_markdown_bold(val)
            if key and val:
                info[key] = val
    return info


def parse_scores(text: str) -> dict[str, int | None]:
    """Extract six dimension scores from the 六维度评分总览 table."""
    scores = {}
    section = extract_section(text, '六维度评分总览')
    if not section:
        return scores
    
    rows = parse_markdown_table(section)
    dim_names = ['人设定位', '互动效果', '粉丝关系', '流水营收', '个人状态', '内容质量']
    
    for row in rows:
        dim = row.get('维度', row.get('**维度**', row.get('**人设定位**', '')))
        dim = strip_markdown_bold(dim)
        
        if not dim:
            first_key = list(row.keys())[0] if row.keys() else ''
            dim = strip_markdown_bold(row.get(first_key, ''))
        
        for dn in dim_names:
            if dn in dim:
                score_str = row.get('评分', row.get('**评分**', ''))
                if not score_str:
                    keys = list(row.keys())
                    if len(keys) >= 2:
                        score_str = row[keys[1]]
                score = parse_score(score_str)
                if score is not None:
                    scores[dn] = score
                break
    
    return scores


def parse_path_signals(text: str) -> dict:
    """Extract 17 path signals from the path signal table."""
    signals = {}
    
    section = None
    for heading in ['17条关系路径信号表', '关系路径信号表', '路径信号表', '关系路径信号']:
        section = extract_section(text, heading)
        if section:
            break
    
    if not section:
        return signals
    
    rows = parse_markdown_table(section)
    for row in rows:
        path_id = row.get('编号', row.get('路径编号', row.get('#', row.get('**编号**', ''))))
        path_id = strip_markdown_bold(path_id)
        
        if not path_id:
            keys = list(row.keys())
            if keys:
                path_id = strip_markdown_bold(row[keys[0]])
        
        signal = row.get('信号强度', row.get('信号', row.get('**信号强度**', row.get('**信号**', ''))))
        signal = strip_markdown_bold(signal)
        
        if not signal:
            keys = list(row.keys())
            for k in keys:
                if '信号' in k or '强度' in k:
                    signal = strip_markdown_bold(row[k])
                    break
        
        if path_id and signal:
            path_id = path_id.strip().replace('*', '').replace(' ', '')
            signals[path_id] = parse_signal_strength(signal)
    
    return signals


def parse_heart_wall(text: str) -> dict:
    """Extract heart wall info (真人主播版——含壁类型)."""
    result = {'type': '未知', 'risk_level': '未知', 'wall_category': '未知'}
    
    for heading in ['心之壁评估', '心之壁判定', '心之壁', '心之壁分析']:
        section = extract_section(text, heading)
        if section:
            break
    else:
        section = None
    
    if not section:
        return result
    
    # Try table parsing first
    rows = parse_markdown_table(section)
    for row in rows:
        key = row.get('维度', row.get('项目', row.get('**维度**', '')))
        key = strip_markdown_bold(key)
        val = row.get('评估', row.get('内容', row.get('**评估**', '')))
        val = strip_markdown_bold(val)
        
        if '类型' in key or '壁类型' in key or '壁' in key:
            result['type'] = val
            # Categorize
            if '机构' in val or '约束' in val or 'MCN' in val.upper():
                result['wall_category'] = '机构约束型'
            elif '外力' in val or '打破' in val or '曝光' in val:
                result['wall_category'] = '外力打破'
            elif '内部' in val or '崩溃' in val:
                result['wall_category'] = '内部崩溃'
            elif '自发' in val or '管理' in val:
                result['wall_category'] = '自发管理型'
            elif '厚' in val:
                result['wall_category'] = '自发管理型'
            elif '薄' in val:
                result['wall_category'] = '自发管理型'
        if '风险' in key:
            result['risk_level'] = val
    
    # If table didn't work, try regex
    if result['type'] == '未知':
        m = re.search(r'(?:心之壁|壁).{0,10}(?:类型|判定)[：:]\s*(.+?)(?:\n|$)', section)
        if not m:
            m = re.search(r'(机构约束型|自发管理型|外力打破|内部崩溃|厚壁|中偏厚|薄壁)', section)
        if m:
            result['type'] = m.group(1).strip()
            val = result['type']
            if '机构' in val or '约束' in val:
                result['wall_category'] = '机构约束型'
            elif '外力' in val or '打破' in val:
                result['wall_category'] = '外力打破'
            elif '内部' in val or '崩溃' in val:
                result['wall_category'] = '内部崩溃'
            elif '厚' in val or '薄' in val:
                result['wall_category'] = '自发管理型'
    
    if result['risk_level'] == '未知':
        m = re.search(r'风险[等级别]*[：:]\s*(.+?)(?:\n|$)', section)
        if not m:
            m = re.search(r'风险[：:]\s*(.{1,20})', section)
        if m:
            result['risk_level'] = m.group(1).strip()
    
    return result


def parse_contradictions(text: str) -> list[str]:
    """Extract contradiction signals."""
    contradictions = []
    
    section = None
    for heading in ['矛盾信号', '核心矛盾', '矛盾与风险', '矛盾信号记录']:
        section = extract_section(text, heading)
        if section:
            break
    
    if not section:
        return contradictions
    
    rows = parse_markdown_table(section)
    for row in rows:
        desc = row.get('描述', row.get('矛盾描述', row.get('矛盾类型', '')))
        desc = strip_markdown_bold(desc)
        if desc and len(desc) > 5:
            contradictions.append(desc)
        
        for k, v in row.items():
            v = strip_markdown_bold(v)
            if len(v) > 10 and ('矛盾' in v or '断裂' in v or '信号' in v):
                if v not in contradictions:
                    contradictions.append(v)
    
    if len(contradictions) < 1:
        for line in section.split('\n'):
            line = line.strip()
            if line.startswith('-') or line.startswith('*'):
                if any(w in line for w in ['矛盾', '断裂', 'C1', 'C2', 'C3', 'C4']):
                    contradictions.append(re.sub(r'^[-*]\s*', '', line).strip()[:200])
    
    return contradictions


def parse_credibility(text: str) -> dict:
    """Extract analysis credibility self-assessment."""
    cred = {}
    section = extract_section(text, '分析可信度|可信度自评')
    if not section:
        return cred
    
    rows = parse_markdown_table(section)
    for row in rows:
        key = list(row.keys())[0] if row.keys() else ''
        val_key = list(row.keys())[1] if len(row.keys()) > 1 else ''
        k = strip_markdown_bold(row.get(key, key))
        v = strip_markdown_bold(row.get(val_key, ''))
        if k and v:
            cred[k.replace('维度', '').replace('**', '').strip()] = v
    return cred


def parse_real_special_factors(text: str) -> dict:
    """Extract 真人主播特殊因子 section."""
    factors = {
        'appearance_pressure': '未知',
        'privacy_risk': '未知', 
        'platform_algo_dependency': '未知'
    }
    
    section = extract_section(text, '真人主播特殊因子')
    if not section:
        return factors
    
    # Look for key patterns
    if '外貌' in section or '形象管理' in section:
        if '有' in section or '高' in section or '是' in section:
            factors['appearance_pressure'] = '有'
        else:
            factors['appearance_pressure'] = '无'
    
    if '私生活' in section or '曝光' in section:
        if '高' in section:
            factors['privacy_risk'] = '高'
        elif '中' in section:
            factors['privacy_risk'] = '中'
        elif '低' in section:
            factors['privacy_risk'] = '低'
    
    if '算法' in section or '平台依赖' in section or '推荐' in section:
        if '高' in section:
            factors['platform_algo_dependency'] = '高'
        elif '中' in section:
            factors['platform_algo_dependency'] = '中'
        elif '低' in section:
            factors['platform_algo_dependency'] = '低'
    
    return factors


# ============================================================
# 3. Metadata Extraction (真人主播版)
# ============================================================

def extract_region_from_info(info: dict) -> str:
    """Extract region from basic info."""
    for k, v in info.items():
        if '地域' in k:
            v = v.strip()
            if '中国' in v or 'CN' in v.upper() or '大陆' in v:
                return '中国大陆'
            if '日本' in v or 'JP' in v.upper():
                return '日本'
            if '英语' in v or 'EN' in v.upper() or 'English' in v:
                return '英语圈'
            if '韩国' in v or 'KR' in v.upper() or 'Korea' in v:
                return '韩国'
            if '印尼' in v or '泰国' in v or '东南亚' in v or 'SEA' in v.upper() or 'Vietnam' in v or 'Philippines' in v:
                return '东南亚及其他'
            if '特殊' in v or 'SP' in v.upper():
                return '特殊案例'
    return '未分类'


def extract_tenure_from_info(info: dict) -> str:
    """Extract tenure category."""
    for k, v in info.items():
        if '时长' in k or '从业' in k:
            v = v.strip()
            if '新人' in v or '0-6' in v:
                return '新人期'
            if '成长' in v:
                return '成长期'
            if '成熟' in v or '2-5' in v:
                return '成熟期'
            if '超长' in v or '5年' in v or '元老' in v or '10年' in v:
                return '超长待机'
            if '退役' in v or '毕业' in v or '休眠' in v or '停播' in v or '淡出' in v or '引退' in v:
                return '停播淡出'
    return '未分类'


def extract_type_from_info(info: dict) -> str:
    """Extract content type (真人主播版分类)."""
    for k, v in info.items():
        if '类型' in k or '内容' in k:
            v = v.strip()
            # IRL/聊天
            if 'IRL' in v.upper() or '聊天' in v or '杂谈' in v or 'chat' in v.lower() or 'just chatting' in v.lower():
                return 'IRL/聊天势'
            # 游戏
            if '游戏' in v or 'game' in v.lower() or 'gaming' in v.lower():
                return '游戏势'
            # 音乐
            if '音乐' in v or '唱歌' in v or '歌' in v or 'music' in v.lower() or 'sing' in v.lower():
                return '音乐势'
            # 舞蹈
            if '舞蹈' in v or 'dance' in v.lower():
                return '舞蹈势'
            # 美妆/时尚
            if '美妆' in v or '时尚' in v or '化妆' in v or '穿搭' in v or 'beauty' in v.lower() or 'fashion' in v.lower() or 'makeup' in v.lower():
                return '美妆/时尚势'
            # 美食/吃播
            if '美食' in v or '吃播' in v or 'food' in v.lower() or 'mukbang' in v.lower() or 'cooking' in v.lower():
                return '美食/吃播势'
            # 健身/运动
            if '健身' in v or '运动' in v or 'fitness' in v.lower() or 'sport' in v.lower() or 'gym' in v.lower():
                return '健身/运动势'
            # 户外/旅行
            if '户外' in v or '旅行' in v or 'travel' in v.lower() or 'outdoor' in v.lower():
                return '户外/旅行势'
            # 知识/播客
            if '知识' in v or '教育' in v or '教学' in v or '播客' in v or 'podcast' in v.lower() or 'educational' in v.lower():
                return '知识/播客势'
            # 带货/电商
            if '带货' in v or '电商' in v or 'shopping' in v.lower() or 'e-commerce' in v.lower():
                return '带货/电商势'
            # 综合
            if '综合' in v or 'variety' in v.lower() or 'mixed' in v.lower():
                return '综合势'
            # ASMR (跨类型)
            if 'ASMR' in v.upper() or 'asmr' in v.lower() or '朗读' in v:
                return '综合势'
    return '综合势'


def extract_state_from_info(info: dict) -> str:
    """Extract activity state (真人主播版——不含退役/毕业)."""
    for k, v in info.items():
        if '状态' in k or '从业' in k:
            v = v.strip()
            if '停播' in v or '淡出' in v or '引退' in v or 'hiatus' in v.lower() or 'retired' in v.lower():
                return '停播淡出'
            if '瓶颈' in v or '休止' in v or '倦怠' in v or 'burnout' in v.lower():
                return '瓶颈'
            if '活跃' in v or 'active' in v.lower() or '現役' in v:
                return '活跃'
    return '活跃'


def extract_org_from_info(info: dict) -> str:
    """Extract organization type (真人主播版)."""
    for k, v in info.items():
        if '组织' in k or '所属' in k or 'organization' in k.lower() or 'agency' in k.lower():
            v = v.strip()
            # 明星/艺人转型
            if '明星' in v or '艺人' in v or 'celebrity' in v.lower() or '转型' in v:
                return '明星转型'
            # 独立主播
            if '独立' in v or '个人' in v or 'indie' in v.lower() or 'independent' in v.lower() or 'solo' in v.lower():
                return '独立'
            # MCN签约
            if 'MCN' in v.upper() or 'mcn' in v.lower() or '签约' in v or '公会' in v or 'agency' in v.lower():
                if '大型' in v or '头部' in v or 'major' in v.lower() or 'top' in v.lower():
                    return 'MCN签约·大型'
                return 'MCN签约·中小型'
            # 平台签约
            if '平台签约' in v or 'Twitch Partner' in v or 'YouTube Partner' in v or '抖音独家' in v or 'partner' in v.lower():
                return '平台签约'
    return '独立'


def extract_scale_from_info(info: dict) -> str:
    """Extract scale tier."""
    for k, v in info.items():
        if '规模' in k or '粉丝' in k or '订阅' in k or 'subscriber' in k.lower() or 'follower' in k.lower():
            v = v.strip()
            nums = re.findall(r'([\d,.]+)\s*万', v)
            if nums:
                n = float(nums[0].replace(',', ''))
                if n >= 300:
                    return '顶级'
                if n >= 100:
                    return '头部'
                if n >= 10:
                    return '腰部'
                if n >= 1:
                    return '中小层'
                return '底层/新人'
            nums_k = re.findall(r'([\d,.]+)\s*[Kk]', v)
            if nums_k:
                n = float(nums_k[0].replace(',', ''))
                if n >= 1000:
                    return '顶级'
                if n >= 300:
                    return '头部'
                if n >= 50:
                    return '腰部'
                if n >= 5:
                    return '中小层'
                return '底层/新人'
            if '顶级' in v or '300万' in v or '500万' in v:
                return '顶级'
            if '头部' in v or '100万' in v:
                return '头部'
            if '腰部' in v or '10万' in v:
                return '腰部'
            if '中小' in v or '1万' in v:
                return '中小层'
            if '底层' in v or '新人' in v or '<1万' in v:
                return '底层/新人'
    return '未分类'


# ============================================================
# 4. Main Extraction
# ============================================================

def extract_one_report(filepath: Path) -> dict | None:
    """Extract all structured data from one report."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        print(f"  ERROR reading {filepath.name}: {e}")
        return None
    
    name = filepath.stem.replace('_六维分析报告', '')
    
    info = parse_basic_info(text)
    scores = parse_scores(text)
    paths = parse_path_signals(text)
    heart_wall = parse_heart_wall(text)
    contradictions = parse_contradictions(text)
    credibility = parse_credibility(text)
    real_factors = parse_real_special_factors(text)
    
    region = extract_region_from_info(info)
    tenure = extract_tenure_from_info(info)
    ctype = extract_type_from_info(info)
    state = extract_state_from_info(info)
    org = extract_org_from_info(info)
    scale = extract_scale_from_info(info)
    
    result = {
        'name': name,
        'file': filepath.name,
        'region': region,
        'state': state,
        'tenure': tenure,
        'type': ctype,
        'scale': scale,
        'org': org,
        'scores': scores,
        'paths': paths,
        'heart_wall': heart_wall,
        'contradictions': contradictions,
        'credibility': credibility,
        'real_special_factors': real_factors,
        '_parse_quality': {
            'scores_count': len(scores),
            'paths_count': len(paths),
            'has_heart_wall': bool(heart_wall.get('type', '未知') != '未知'),
            'has_contradictions': len(contradictions) > 0,
        }
    }
    
    return result


def extract_all_reports() -> list[dict]:
    """Extract all reports and return list of structured data."""
    report_files = sorted(REPORTS_DIR.glob('*_六维分析报告.md'))
    results = []
    errors = []
    
    for i, fp in enumerate(report_files):
        print(f"  [{i+1}/{len(report_files)}] {fp.name}...", end=' ')
        data = extract_one_report(fp)
        if data:
            if data['_parse_quality']['scores_count'] >= 5:
                results.append(data)
                print(f"OK (scores:{data['_parse_quality']['scores_count']}, paths:{data['_parse_quality']['paths_count']})")
            else:
                errors.append((fp.name, f"scores_count={data['_parse_quality']['scores_count']}"))
                print(f"SKIP (insufficient scores: {data['_parse_quality']['scores_count']})")
                results.append(data)
        else:
            errors.append((fp.name, "parse failed"))
            print("FAILED")
    
    if errors:
        print(f"\n  Errors/Skips ({len(errors)}):")
        for name, reason in errors:
            print(f"    - {name}: {reason}")
    
    return results


# ============================================================
# 5. Statistics Computation
# ============================================================

def compute_stats(raw_data: list[dict]) -> dict:
    """Compute all statistics for l0_stats.json."""
    stats = {}
    
    valid = [d for d in raw_data if d['_parse_quality']['scores_count'] >= 5]
    
    dims = ['人设定位', '互动效果', '粉丝关系', '流水营收', '个人状态', '内容质量']
    
    def desc_stats(values: list[float]) -> dict:
        if not values:
            return {'mean': None, 'median': None, 'std': None, 'min': None, 'max': None, 'count': 0}
        n = len(values)
        mean = sum(values) / n
        sorted_vals = sorted(values)
        median = sorted_vals[n // 2] if n % 2 == 1 else (sorted_vals[n//2 - 1] + sorted_vals[n//2]) / 2
        variance = sum((v - mean) ** 2 for v in values) / n
        std = math.sqrt(variance)
        return {
            'mean': round(mean, 2),
            'median': round(median, 2),
            'std': round(std, 2),
            'min': min(values),
            'max': max(values),
            'count': n
        }
    
    def group_stats(data: list[dict], group_key: str) -> dict:
        groups = defaultdict(list)
        for d in data:
            g = d.get(group_key, '未分类')
            groups[g].append(d)
        
        result = {}
        for g, items in sorted(groups.items()):
            dim_stats = {}
            for dim in dims:
                vals = [item['scores'].get(dim) for item in items if item['scores'].get(dim) is not None]
                dim_stats[dim] = desc_stats(vals)
            result[g] = {
                'count': len(items),
                'dimensions': dim_stats
            }
        return result
    
    # Full sample stats
    full_dim_stats = {}
    for dim in dims:
        vals = [d['scores'].get(dim) for d in valid if d['scores'].get(dim) is not None]
        full_dim_stats[dim] = desc_stats(vals)
    
    stats['full_sample'] = {
        'total_reports': len(raw_data),
        'valid_reports': len(valid),
        'dimensions': full_dim_stats
    }
    
    # Grouped stats
    for group_key, label in [('region', 'by_region'), ('type', 'by_type'), ('scale', 'by_scale'), ('state', 'by_state'), ('org', 'by_org')]:
        stats[label] = group_stats(valid, group_key)
    
    # Path signal stats
    path_stats = defaultdict(lambda: {'total': 0, '强': 0, '中': 0, '弱': 0, '沉默': 0, '不足': 0, '不适用': 0})
    for d in valid:
        for pid, signal in d['paths'].items():
            path_stats[pid]['total'] += 1
            if signal in path_stats[pid]:
                path_stats[pid][signal] += 1
    
    path_result = {}
    for pid, counts in sorted(path_stats.items()):
        total = counts['total']
        if total == 0:
            continue
        detected = counts['强'] + counts['中'] + counts['弱']
        path_result[pid] = {
            'total': total,
            'detection_rate': round(detected / total * 100, 1) if total > 0 else 0,
            'strong_rate': round(counts['强'] / total * 100, 1),
            'medium_rate': round(counts['中'] / total * 100, 1),
            'weak_rate': round(counts['弱'] / total * 100, 1),
            'silent_rate': round(counts['沉默'] / total * 100, 1),
            'insufficient_rate': round(counts['不足'] / total * 100, 1),
            'na_rate': round(counts['不适用'] / total * 100, 1),
        }
    stats['path_signals'] = path_result
    
    # Contradiction rate
    contradiction_count = Counter()
    for d in valid:
        for c in d.get('contradictions', []):
            if '④断裂' in c or '互动→营收' in c or '交易型互惠' in c:
                contradiction_count['④互动→营收断裂'] += 1
            elif '⑥' in c or '状态→人设' in c or '前台崩塌' in c:
                contradiction_count['⑥状态→人设·前台崩塌'] += 1
            elif '②' in c or '互动→粉丝' in c:
                contradiction_count['②互动→粉丝关系'] += 1
            elif '⑨' in c:
                contradiction_count['⑨时长→状态'] += 1
            else:
                contradiction_count['其他矛盾信号'] += 1
    
    stats['contradiction_frequency'] = dict(contradiction_count.most_common(20))
    
    # Heart wall distribution
    heart_wall_types = Counter()
    heart_wall_categories = Counter()
    heart_wall_risks = Counter()
    for d in valid:
        hw = d.get('heart_wall', {})
        heart_wall_types[hw.get('type', '未知')] += 1
        heart_wall_categories[hw.get('wall_category', '未知')] += 1
        heart_wall_risks[hw.get('risk_level', '未知')] += 1
    stats['heart_wall_distribution'] = {
        'by_type': dict(heart_wall_types.most_common()),
        'by_category': dict(heart_wall_categories.most_common()),
        'by_risk': dict(heart_wall_risks.most_common())
    }
    
    # Heart wall cross table (厚壁×停播淡出)
    thick_retired = 0
    thick_active = 0
    thin_retired = 0
    thin_active = 0
    for d in valid:
        hw_type = d.get('heart_wall', {}).get('type', '')
        is_thick = '厚' in hw_type or '机构' in hw_type
        is_retired = d.get('state', '') == '停播淡出'
        if is_thick and is_retired:
            thick_retired += 1
        elif is_thick and not is_retired:
            thick_active += 1
        elif not is_thick and is_retired:
            thin_retired += 1
        elif not is_thick and not is_retired:
            thin_active += 1
    
    stats['heart_wall_cross_table'] = {
        'thick_retired': thick_retired,
        'thick_active': thick_active,
        'thin_retired': thin_retired,
        'thin_active': thin_active,
        'thick_wall_pseudo_stability_rate': round(thick_retired / (thick_retired + thick_active) * 100, 1) if (thick_retired + thick_active) > 0 else 0
    }
    
    # Real streamer special factors
    appearance_count = Counter(d.get('real_special_factors', {}).get('appearance_pressure', '未知') for d in valid)
    privacy_count = Counter(d.get('real_special_factors', {}).get('privacy_risk', '未知') for d in valid)
    algo_count = Counter(d.get('real_special_factors', {}).get('platform_algo_dependency', '未知') for d in valid)
    stats['real_special_factors'] = {
        'appearance_pressure': dict(appearance_count),
        'privacy_risk': dict(privacy_count),
        'platform_algo_dependency': dict(algo_count)
    }
    
    # Outlier detection (Z-score > 1.5 within groups)
    outliers = []
    
    region_groups = defaultdict(list)
    for d in valid:
        region_groups[d.get('region', '未分类')].append(d)
    
    for region, items in region_groups.items():
        for dim in dims:
            vals = [(d, d['scores'].get(dim)) for d in items if d['scores'].get(dim) is not None]
            if len(vals) < 3:
                continue
            scores_only = [v[1] for v in vals]
            mean = sum(scores_only) / len(scores_only)
            std = math.sqrt(sum((s - mean)**2 for s in scores_only) / len(scores_only)) if len(scores_only) > 1 else 0
            if std == 0:
                continue
            for d, s in vals:
                z = (s - mean) / std
                if abs(z) > 1.5 or abs(s - mean) >= 2:
                    outliers.append({
                        'name': d['name'],
                        'dimension': dim,
                        'score': s,
                        'group': region,
                        'group_mean': round(mean, 2),
                        'z_score': round(z, 2),
                        'deviation': round(s - mean, 2)
                    })
    
    stats['outliers'] = sorted(outliers, key=lambda x: abs(x['z_score']), reverse=True)[:50]
    
    # Regional difference matrix
    regions_list = sorted(set(d.get('region', '未分类') for d in valid))
    dim_means_by_region = {}
    for region in regions_list:
        region_data = [d for d in valid if d.get('region') == region]
        dim_means = {}
        for dim in dims:
            vals = [d['scores'].get(dim) for d in region_data if d['scores'].get(dim) is not None]
            if vals:
                dim_means[dim] = round(sum(vals) / len(vals), 2)
        dim_means_by_region[region] = dim_means
    
    differences = []
    for i, r1 in enumerate(regions_list):
        for r2 in regions_list[i+1:]:
            for dim in dims:
                v1 = dim_means_by_region.get(r1, {}).get(dim)
                v2 = dim_means_by_region.get(r2, {}).get(dim)
                if v1 is not None and v2 is not None:
                    diff = round(v1 - v2, 2)
                    if abs(diff) >= 1.0:
                        differences.append({
                            'region1': r1,
                            'region2': r2,
                            'dimension': dim,
                            'diff': diff
                        })
    
    stats['regional_differences'] = {
        'dim_means_by_region': dim_means_by_region,
        'significant_diffs': sorted(differences, key=lambda x: abs(x['diff']), reverse=True)
    }
    
    return stats


# ============================================================
# 6. Report Index Generation
# ============================================================

def generate_report_index(raw_data: list[dict], output_path: Path):
    """Generate 00_报告索引.md."""
    lines = []
    lines.append('# 六维分析报告索引（真人主播）\n')
    lines.append(f'> 索引生成时间：2026-06-25\n')
    lines.append(f'> 报告总数：{len(raw_data)} 份\n')
    lines.append('')
    lines.append('| 序号 | 主播名 | 地域 | 状态 | 时长 | 类型 | 规模 | 组织 | 心之壁类型 | 人设 | 互动 | 粉丝 | 营收 | 状态 | 内容 | 报告链接 |')
    lines.append('|------|--------|------|------|------|------|------|------|---------|------|------|------|------|------|------|---------|')
    
    for i, d in enumerate(raw_data):
        name = d['name']
        region = d.get('region', '—')
        state = d.get('state', '—')
        tenure = d.get('tenure', '—')
        ctype = d.get('type', '—')
        scale = d.get('scale', '—')
        org = d.get('org', '—')
        hw = d.get('heart_wall', {}).get('wall_category', '—')
        
        scores = d.get('scores', {})
        s1 = str(scores.get('人设定位', '—'))
        s2 = str(scores.get('互动效果', '—'))
        s3 = str(scores.get('粉丝关系', '—'))
        s4 = str(scores.get('流水营收', '—'))
        s5 = str(scores.get('个人状态', '—'))
        s6 = str(scores.get('内容质量', '—'))
        
        filename = d.get('file', f'{name}_六维分析报告.md')
        link = f'[报告](./{filename})'
        
        lines.append(f'| {i+1} | {name} | {region} | {state} | {tenure} | {ctype} | {scale} | {org} | {hw} | {s1} | {s2} | {s3} | {s4} | {s5} | {s6} | {link} |')
    
    # Summary
    lines.append('')
    lines.append('## 统计概要')
    lines.append('')
    
    region_counts = Counter(d.get('region', '未分类') for d in raw_data)
    lines.append('### 按地域分布')
    lines.append('')
    lines.append('| 地域 | 数量 |')
    lines.append('|------|:---:|')
    for r, c in region_counts.most_common():
        lines.append(f'| {r} | {c} |')
    lines.append(f'| **合计** | **{len(raw_data)}** |')
    
    state_counts = Counter(d.get('state', '未分类') for d in raw_data)
    lines.append('')
    lines.append('### 按从业状态分布')
    lines.append('')
    lines.append('| 状态 | 数量 |')
    lines.append('|------|:---:|')
    for s, c in state_counts.most_common():
        lines.append(f'| {s} | {c} |')
    
    type_counts = Counter(d.get('type', '未分类') for d in raw_data)
    lines.append('')
    lines.append('### 按内容类型分布')
    lines.append('')
    lines.append('| 类型 | 数量 |')
    lines.append('|------|:---:|')
    for t, c in type_counts.most_common():
        lines.append(f'| {t} | {c} |')
    
    org_counts = Counter(d.get('org', '未分类') for d in raw_data)
    lines.append('')
    lines.append('### 按组织属性分布')
    lines.append('')
    lines.append('| 组织属性 | 数量 |')
    lines.append('|------|:---:|')
    for o, c in org_counts.most_common():
        lines.append(f'| {o} | {c} |')
    
    content = '\n'.join(lines) + '\n'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  Generated: {output_path}")


# ============================================================
# 7. Main
# ============================================================

def main():
    print("=" * 60)
    print("Phase 3 L0: 代码预处理(真人主播版) - 从报告中提取结构化数据")
    print("=" * 60)
    
    print("\n[1/4] 提取报告数据...")
    raw_data = extract_all_reports()
    print(f"  成功提取: {len(raw_data)} 份报告")
    
    print("\n[2/4] 保存 l0_raw.json...")
    raw_output = BASE_DIR / "l0_raw.json"
    with open(raw_output, 'w', encoding='utf-8') as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)
    print(f"  已保存: {raw_output}")
    
    print("\n[3/4] 计算统计数据...")
    stats = compute_stats(raw_data)
    stats_output = BASE_DIR / "l0_stats.json"
    with open(stats_output, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"  已保存: {stats_output}")
    
    full = stats.get('full_sample', {})
    print(f"\n  === 全样本统计摘要 ===")
    print(f"  总报告数: {full.get('total_reports', 0)}")
    print(f"  有效报告数(≥5维评分): {full.get('valid_reports', 0)}")
    dims_stats = full.get('dimensions', {})
    for dim, ds in dims_stats.items():
        if ds.get('mean') is not None:
            print(f"  {dim}: 均值={ds['mean']}, 中位数={ds['median']}, std={ds['std']}, range=[{ds['min']}, {ds['max']}]")
    
    # Real special factors
    rsf = stats.get('real_special_factors', {})
    if rsf:
        print(f"\n  === 真人主播特殊因子 ===")
        print(f"  外貌管理压力: {rsf.get('appearance_pressure', {})}")
        print(f"  私生活曝光风险: {rsf.get('privacy_risk', {})}")
        print(f"  平台算法依赖: {rsf.get('platform_algo_dependency', {})}")
    
    print("\n[4/4] 生成 00_报告索引.md...")
    index_path = REPORTS_DIR / "00_报告索引.md"
    generate_report_index(raw_data, index_path)
    
    print("\n" + "=" * 60)
    print("Phase 3 L0 完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
