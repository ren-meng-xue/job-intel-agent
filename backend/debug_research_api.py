import requests
import json
import time
import os

BASE_URL = "http://localhost:8001/api/v1"
EMAIL = "test_final@example.com"
PASSWORD = "password123"
JD_URL = "https://www.zhipin.com/job_detail/c6643409d590546d0nZ439y_EFtZ.html"
RESUME_PATH = "/Users/xuebao/learn/面试/任孟雪WEB前端工程师.pdf"

def parse_sse(response):
    """简单的 SSE 解析器"""
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data: '):
                yield decoded_line[6:]

def test_api():
    print(f"=== Starting API Test Flow ===")
    
    # 1. Login
    print(f"\n[1/6] Logging in as {EMAIL}...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if resp.status_code != 200:
        print(f"FAILED: {resp.status_code} - {resp.text}")
        return
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"SUCCESS: Login successful.")

    # 2. Upload Resume
    print(f"\n[2/6] Uploading resume: {os.path.basename(RESUME_PATH)}...")
    with open(RESUME_PATH, 'rb') as f:
        files = {
            "file": (os.path.basename(RESUME_PATH), f, "application/pdf")
        }
        resp = requests.post(f"{BASE_URL}/resume/", headers=headers, files=files)
    if resp.status_code not in (200, 201, 202):
        print(f"FAILED: {resp.status_code} - {resp.text}")
        return
    resume_id = resp.json()["id"]
    print(f"SUCCESS: Resume uploaded, ID: {resume_id}")

    # 3. Create Job
    print(f"\n[3/6] Submitting JD URL...")
    resp = requests.post(f"{BASE_URL}/jobs/", headers=headers, json={
        "url": JD_URL,
        "resume_id": resume_id
    })
    if resp.status_code != 201:
        print(f"FAILED: {resp.status_code} - {resp.text}")
        return
    job_id = resp.json()["id"]
    print(f"SUCCESS: Job created, ID: {job_id}, Status: {resp.json()['status']}")

    # 4. Wait for Parse (using SSE)
    print(f"\n[4/6] Waiting for JD parsing (via SSE)...")
    parsed_data = None
    sse_url = f"{BASE_URL}/reports/{job_id}/stream?token={token}"
    response = requests.get(sse_url, stream=True, headers=headers)
    
    for msg_data in parse_sse(response):
        if not msg_data or msg_data == "keep-alive": continue
        try:
            data = json.loads(msg_data)
            print(f"  > SSE Event: {data.get('type')} - {data.get('message', '')}")
            if data.get("type") == "parsed":
                parsed_data = data
                break
            if data.get("type") == "error":
                print(f"FAILED: {data.get('message')}")
                return
        except: continue
            
    if not parsed_data:
        print("FAILED: Did not receive parsed event.")
        return

    # 5. Confirm Job
    print(f"\n[5/6] Confirming JD information...")
    confirm_payload = {
        "title": parsed_data.get("title", "Frontend Engineer"),
        "company": parsed_data.get("company", "ByteDance"),
        "requirements": parsed_data.get("requirements", []),
        "jd_summary": parsed_data.get("jd_summary", "JD Summary"),
        "salary_range": parsed_data.get("salary_range"),
        "location": parsed_data.get("location"),
        "work_type": parsed_data.get("work_type")
    }
    resp = requests.post(f"{BASE_URL}/jobs/{job_id}/confirm", headers=headers, json=confirm_payload)
    if resp.status_code != 200:
        print(f"FAILED: {resp.status_code} - {resp.text}")
        return
    suggested_directions = resp.json().get("suggested_directions", [])
    print(f"SUCCESS: JD confirmed. Suggested directions: {suggested_directions}")

    # 6. Start Research
    print(f"\n[6/6] Starting Research (The stage in your image)...")
    start_payload = {
        "selected_directions": suggested_directions[:4] if suggested_directions else ["公司近期动态", "面试风格&题型"]
    }
    resp = requests.post(f"{BASE_URL}/jobs/{job_id}/start", headers=headers, json=start_payload)
    if resp.status_code != 200:
        print(f"FAILED: {resp.status_code} - {resp.text}")
        return
    print(f"SUCCESS: Research started, Status: {resp.json()['status']}")

    print(f"\n=== Monitoring Research Progress (This will take 3-5 minutes) ===")
    response = requests.get(sse_url, stream=True, headers=headers)
    for msg_data in parse_sse(response):
        if not msg_data or msg_data == "keep-alive": continue
        try:
            data = json.loads(msg_data)
            if data.get("type") == "progress":
                print(f"  [AI PROGRESS] {data.get('message', data.get('node'))}")
            elif data.get("type") == "completed":
                print(f"\nSUCCESS: Report generation complete!")
                break
            elif data.get("type") == "error":
                print(f"\nFAILED: {data.get('message')}")
                break
        except: continue

if __name__ == "__main__":
    test_api()
