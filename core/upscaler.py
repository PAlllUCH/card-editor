import os
import requests
import json
import time
import subprocess

def upload_to_kie(file_path, api_key):
    """Uploads a local file to Kie.ai temporary storage.
    Returns the public download URL on success.
    """
    url = "https://kieai.redpandaai.co/api/file-stream-upload"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    file_name = os.path.basename(file_path)
    
    # We open in binary mode
    with open(file_path, 'rb') as f:
        files = {
            'file': (file_name, f, 'image/png')
        }
        data = {
            'uploadPath': 'images/user-uploads',
            'fileName': file_name
        }
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        
        resp_json = response.json()
        if not resp_json.get("success"):
            raise ValueError(f"Upload failed: {resp_json.get('msg', 'Unknown error')}")
            
        download_url = resp_json.get("data", {}).get("downloadUrl")
        if not download_url:
            raise ValueError("No downloadUrl in upload response data")
            
        return download_url

def get_kie_credits(api_key):
    """Fetches the remaining credits for the KIE.ai account.
    Returns the numeric credit balance on success.
    """
    url = "https://api.kie.ai/api/v1/chat/credit"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    resp_json = response.json()
    if resp_json.get("code") == 200:
        return float(resp_json.get("data", 0))
    raise ValueError(f"Failed to fetch credits (Code {resp_json.get('code')}): {resp_json.get('msg')}")

def create_upscale_task(model, image_url, api_key, upscale_factor="2", extra_params=None, custom_prompt=None):
    """Submits the upscaling task to Kie.ai.
    Returns the task ID.
    """
    url = "https://api.kie.ai/api/v1/jobs/createTask"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Use the custom prompt if provided, otherwise fall back to the default
    if custom_prompt and custom_prompt.strip():
        actual_prompt = custom_prompt.strip()
    else:
        actual_prompt = "Perfectly upscale and enhance this image. Preserve all original text, details, and composition exactly."

    if model == "topaz/image-upscale":
        payload_input = {
            "image_url": image_url,
            "upscale_factor": str(upscale_factor)
        }
    elif model.startswith("nano-banana-2"):
        resolution = "2K" if "2k" in model.lower() else "1K"
        model = "nano-banana-2" 
        payload_input = {
            "image_input": [image_url],
            "resolution": resolution,
            "prompt": actual_prompt
        }
    elif model.startswith("gpt-image-2"):
        resolution = "2K" if "2k" in model.lower() else "1K"
        model = "gpt-image-2-image-to-image" 
        payload_input = {
            "input_urls": [image_url],
            "resolution": resolution,
            "prompt": actual_prompt
        }
    else:
        payload_input = {
            "image": image_url
        }
        
    if extra_params and isinstance(extra_params, dict):
        payload_input.update(extra_params)
        
    payload = {
        "model": model,
        "input": payload_input
    }
        
    response = requests.post(url, headers=headers, json=payload)
    
    if not response.ok:
        try:
            error_json = response.json()
            raise ValueError(f"HTTP {response.status_code}: {error_json.get('msg', error_json)}")
        except ValueError as e:
            if "HTTP" in str(e): raise e
            response.raise_for_status()
    
    resp_json = response.json()
    
    task_id = resp_json.get("taskId")
    data_field = resp_json.get("data")
    
    if not task_id and isinstance(data_field, dict):
        task_id = data_field.get("taskId")
        
    if not task_id:
        error_msg = resp_json.get("msg") or resp_json.get("error") or "Unknown API error"
        raise ValueError(f"API Rejected Task: {error_msg} (Full response: {resp_json})")
        
    return task_id

def poll_task_status(task_id, api_key, log_fn=None, poll_interval=5, timeout=300, stop_check_fn=None):
    """Polls Kie.ai for the upscale task status with support for immediate cancellation."""
    url = f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # NEW: Check for immediate UI cancellation signal
        if stop_check_fn and stop_check_fn():
            raise InterruptedError("Polling aborted by user request.")

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            resp_json = response.json()
            
            data = resp_json.get("data", {}) or resp_json
            state = data.get("state") or data.get("status") or resp_json.get("status")
            
            if log_fn:
                log_fn(f"Task status: {state}")
                
            if state == "success":
                result_json_str = data.get("resultJson")
                result_urls = []
                if result_json_str:
                    try:
                        res_obj = json.loads(result_json_str)
                        if isinstance(res_obj, dict):
                            result_urls = res_obj.get("resultUrls", []) or res_obj.get("result", [])
                    except Exception:
                        pass
                
                if not result_urls:
                    result_urls = data.get("resultUrls") or data.get("result") or data.get("output")
                if not result_urls and "result" in resp_json:
                    result_urls = resp_json["result"]
                if isinstance(result_urls, str):
                    result_urls = [result_urls]
                    
                if result_urls and len(result_urls) > 0:
                    return result_urls[0]
                else:
                    raise ValueError(f"Task succeeded but no output URLs found. Response: {resp_json}")
                    
            elif state in ("fail", "failed", "error"):
                error_msg = data.get('failMsg') or data.get('error') or data.get('errorMessage') or data.get('message') or resp_json.get('error')
                if not error_msg:
                    for field in ('msg', 'message'):
                        val = data.get(field) or resp_json.get(field)
                        if val and val != "success":
                            error_msg = val
                            break
                if not error_msg:
                    error_msg = "Unknown error details"
                
                fail_code_str = f" (Code: {data.get('failCode')})" if data.get('failCode') else ""
                raise ValueError(f"Upscale task failed: {error_msg}{fail_code_str}.")
                
        except Exception as e:
            if log_fn:
                log_fn(f"Error while polling: {str(e)}")
            if "failed" in str(e).lower() or "fail" in str(e).lower() or "aborted" in str(e).lower():
                raise e
                
        # Split sleep interval to stay responsive to stop signals during delay
        for _ in range(poll_interval * 2):
            if stop_check_fn and stop_check_fn():
                raise InterruptedError("Polling aborted by user request.")
            time.sleep(0.5)
        
    raise TimeoutError("Task timed out before completion.")

def download_file(url, output_path):
    """Downloads the upscaled file from the URL to the output path."""
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(8192):
            f.write(chunk)

def upscale_image_pipeline(file_path, model, api_key, output_dir, upscale_factor="2", log_fn=None, extra_params=None, custom_prompt=None, stop_check_fn=None):
    """Full pipeline to upscale a single image using Kie.ai."""
    if stop_check_fn and stop_check_fn():
        raise InterruptedError("Pipeline cancelled before upload.")

    if log_fn:
        log_fn(f"Step 1: Uploading '{os.path.basename(file_path)}' to Kie.ai...")
    download_url = upload_to_kie(file_path, api_key)
    
    if stop_check_fn and stop_check_fn():
        raise InterruptedError("Pipeline cancelled after upload.")

    if log_fn:
        log_fn(f"Uploaded successfully. Temp URL: {download_url}")
        log_fn(f"Step 2: Submitting upscale task with model '{model}'...")
        
    task_id = create_upscale_task(model, download_url, api_key, upscale_factor, extra_params, custom_prompt)
    
    if log_fn:
        log_fn(f"Task submitted successfully. Task ID: {task_id}")
        log_fn("Step 3: Polling for task completion...")
        
    # Pass the stop checkpoint to the polling routine
    result_url = poll_task_status(task_id, api_key, log_fn, stop_check_fn=stop_check_fn)
    
    if log_fn:
        log_fn(f"Result URL received: {result_url}")
        log_fn("Step 4: Downloading upscaled image...")
        
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.normpath(os.path.join(output_dir, f"{base_name}_upscaled.png"))
    
    download_file(result_url, output_path)
    return output_path

def upscale_image_local_upscayl(file_path, model, upscayl_bin, output_dir, upscale_factor="4", log_fn=None, stop_check_fn=None):
    """Pipeline to upscale a single image locally using the Upscayl CLI binary with active process kill logic."""
    if log_fn:
        log_fn(f"Starting local Upscayl processing for '{os.path.basename(file_path)}'...")

    upscayl_bin = os.path.normpath(upscayl_bin)
    file_path = os.path.normpath(file_path)
    output_dir = os.path.normpath(output_dir)

    if not os.path.exists(upscayl_bin):
        raise FileNotFoundError(f"Upscayl binary not found at specified path: {upscayl_bin}")

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.normpath(os.path.join(output_dir, f"{base_name}_upscaled.png"))

    bin_dir = os.path.dirname(upscayl_bin)
    models_dir = os.path.abspath(os.path.join(bin_dir, "..", "models")).replace("\\", "/")

    cmd = [upscayl_bin, "-i", file_path, "-o", output_path, "-m", models_dir, "-n", model, "-s", str(upscale_factor), "-f", "png"]

    if log_fn:
        log_fn(f"Running command: {' '.join([f'\"{x}\"' if ' ' in x else x for x in cmd])}")

    if stop_check_fn and stop_check_fn():
        raise InterruptedError("Upscayl processing stopped by user before launch.")

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=False, cwd=bin_dir)
    
    if process.stdout:
        for line in process.stdout:
            # NEW: Actively kill the running executable if the user hits "Stop" mid-generation
            if stop_check_fn and stop_check_fn():
                process.terminate()
                process.wait()
                raise InterruptedError("Upscayl process terminated mid-execution by user command.")
                
            if log_fn and line.strip():
                log_fn(f"[Upscayl] {line.strip()}")
                
    process.wait()

    if process.returncode != 0:
        raise RuntimeError(f"Upscayl process exited with error code {process.returncode}")

    if log_fn:
        log_fn(f"Local upscaling completed! Saved to '{output_path}'")

    return output_path