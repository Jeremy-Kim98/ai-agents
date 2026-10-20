"""Linear GraphQL 도우미.

개인 API 키는 Authorization 헤더에 그대로 넣는다 (Bearer 없음).
첨부 파일(uploads.linear.app)도 같은 헤더로 내려받는다.
"""
import os
import re

import requests

from agents import config

API = "https://api.linear.app/graphql"
UPLOAD_RE = re.compile(r"(?:!?\[([^\]]*)\]\()?(https://uploads\.linear\.app/[^\s)\"'>]+)\)?")
LABEL_COLORS = {"야간작업": "#5E6AD2", "야간완료": "#4CB782", "레이더": "#F2994A"}


class LinearError(RuntimeError):
    pass


def enabled():
    return os.getenv("LINEAR_API_KEY", "").startswith("lin_api_") and bool(config.LINEAR_TEAM_KEY)


def _headers():
    key = os.getenv("LINEAR_API_KEY", "")
    if not key:
        raise LinearError("LINEAR_API_KEY가 비어 있습니다")
    return {"Authorization": key, "Content-Type": "application/json"}


def gql(query, variables=None):
    r = requests.post(API, json={"query": query, "variables": variables or {}},
                      headers=_headers(), timeout=30)
    try:
        data = r.json()
    except ValueError:
        r.raise_for_status()
        raise
    if data.get("errors"):
        raise LinearError(data["errors"][0].get("message", "알 수 없는 Linear 오류"))
    r.raise_for_status()
    return data["data"]


# ---------------------------------------------------------------- 팀·라벨·상태
def viewer():
    return gql("query { viewer { name email } organization { name urlKey } }")


def teams():
    return gql("query { teams(first: 50) { nodes { id key name } } }")["teams"]["nodes"]


def team(key=None):
    key = key or config.LINEAR_TEAM_KEY
    nodes = gql("""query($key: String!) { teams(filter: { key: { eq: $key } }) {
        nodes { id key name states { nodes { id name type } } } } }""", {"key": key})["teams"]["nodes"]
    if not nodes:
        raise LinearError(f"팀 키 '{key}'를 찾을 수 없습니다. python -m agents.linear_setup으로 확인하세요")
    return nodes[0]


def find_label(name, team_id):
    nodes = gql("""query($name: String!) { issueLabels(first: 50, filter: { name: { eq: $name } }) {
        nodes { id name team { id } } } }""", {"name": name})["issueLabels"]["nodes"]
    for n in nodes:  # 팀 라벨 우선, 없으면 워크스페이스 공통 라벨
        if n["team"] and n["team"]["id"] == team_id:
            return n["id"]
    for n in nodes:
        if not n["team"]:
            return n["id"]
    return None


def ensure_label(name, team_id):
    lid = find_label(name, team_id)
    if lid:
        return lid, False
    res = gql("""mutation($input: IssueLabelCreateInput!) { issueLabelCreate(input: $input) {
        success issueLabel { id } } }""",
              {"input": {"name": name, "teamId": team_id, "color": LABEL_COLORS.get(name, "#95A2B3")}})
    return res["issueLabelCreate"]["issueLabel"]["id"], True


def state_id(team_obj, name):
    for s in team_obj["states"]["nodes"]:
        if s["name"].strip().lower() == name.strip().lower():
            return s["id"]
    return None


# ---------------------------------------------------------------- 이슈
ISSUE_FIELDS = """id identifier title description url
    team { id key }
    state { name type }
    labels { nodes { id name } }
    comments(first: 50) { nodes { body createdAt user { name } } }"""


def queued_issues(limit):
    q = f"""query($label: String!, $team: String!, $n: Int!) {{
      issues(first: $n, filter: {{
        labels: {{ name: {{ eq: $label }} }},
        team: {{ key: {{ eq: $team }} }},
        state: {{ type: {{ nin: ["completed", "canceled"] }} }}
      }}) {{ nodes {{ {ISSUE_FIELDS} }} }} }}"""
    return gql(q, {"label": config.NIGHT_LABEL, "team": config.LINEAR_TEAM_KEY, "n": limit})["issues"]["nodes"]


def issue_by_identifier(identifier):
    return gql(f"query($id: String!) {{ issue(id: $id) {{ {ISSUE_FIELDS} }} }}", {"id": identifier})["issue"]


def comment(issue_id, body):
    gql("""mutation($input: CommentCreateInput!) { commentCreate(input: $input) { success } }""",
        {"input": {"issueId": issue_id, "body": body}})


def update_issue(issue_id, **fields):
    gql("""mutation($id: String!, $input: IssueUpdateInput!) { issueUpdate(id: $id, input: $input) { success } }""",
        {"id": issue_id, "input": fields})


def create_issue(team_id, title, description, label_ids):
    res = gql("""mutation($input: IssueCreateInput!) { issueCreate(input: $input) {
        success issue { id identifier url } } }""",
              {"input": {"teamId": team_id, "title": title[:250], "description": description,
                         "labelIds": label_ids}})
    return res["issueCreate"]["issue"]


def download(url, max_mb):
    """uploads.linear.app 파일만 인증 헤더를 붙여 내려받는다."""
    if not url.startswith("https://uploads.linear.app/"):
        raise LinearError("Linear 업로드 주소가 아닙니다")
    with requests.get(url, headers={"Authorization": _headers()["Authorization"]},
                      timeout=60, stream=True) as r:
        r.raise_for_status()
        data = b""
        for chunk in r.iter_content(1 << 20):
            data += chunk
            if len(data) > max_mb * 1024 * 1024:
                raise LinearError(f"파일이 {max_mb}MB를 넘습니다")
        return data, r.headers.get("content-type", "")


def upload_links(text):
    """마크다운 속 Linear 첨부 링크를 (표시 이름, url)로 뽑는다 (중복 제거)."""
    seen, out = set(), []
    for name, url in UPLOAD_RE.findall(text or ""):
        if url not in seen:
            seen.add(url)
            out.append((name.strip(), url))
    return out


# ---------------------------------------------------------------- 레이더 연동
def radar_to_linear(items):
    """중요도 높은 레이더 항목을 Linear 이슈로 등록하고, 항목에 이슈 번호를 붙인다."""
    if not enabled():
        return
    picks = [i for i in items if i["importance"] >= config.RADAR_TO_LINEAR_MIN_IMPORTANCE]
    if not picks:
        return
    t = team()
    label_id, _ = ensure_label(config.RADAR_LABEL, t["id"])
    for it in picks:
        mark = {"ok": "원문 일치 확인", "unknown": "자동 확인 불가"}.get(it.get("quote_status"), "")
        lines = [f"**요약**  {it['summary']}"]
        if it["why"]:
            lines.append(f"**왜 중요한가**  {it['why']}")
        if it.get("apply"):
            lines.append(f"**내 연구 적용**  {it['apply']}")
        lines.append(f"**출처**  [{it['source'] or it['url']}]({it['url']}) {it['date']}")
        if it.get("quote"):
            lines.append(f"> “{it['quote']}”  ({mark})")
        lines.append("\n_로봇+AI 레이더 자동 등록. 관심 있으면 진행, 아니면 Cancel하면 다음 레이더가 참고합니다._")
        issue = create_issue(t["id"], f"[레이더] {it['title']}", "\n\n".join(lines), [label_id])
        it["linear_id"], it["linear_url"] = issue["identifier"], issue["url"]


def radar_feedback(limit=10):
    """최근 6주간 레이더 이슈 중 완료한 것과 취소한 것의 제목."""
    if not enabled():
        return [], []
    nodes = gql("""query($label: String!) { issues(first: 100, filter: {
        labels: { name: { eq: $label } }, updatedAt: { gt: "-P6W" } }) {
        nodes { title state { type } } } }""", {"label": config.RADAR_LABEL})["issues"]["nodes"]
    clean = lambda t: t.removeprefix("[레이더] ").strip()
    done = [clean(n["title"]) for n in nodes if n["state"]["type"] in ("started", "completed")][:limit]
    dropped = [clean(n["title"]) for n in nodes if n["state"]["type"] == "canceled"][:limit]
    return done, dropped
