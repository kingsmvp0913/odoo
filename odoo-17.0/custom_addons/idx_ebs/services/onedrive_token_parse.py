import requests
import json
import base64
from datetime import datetime


def comprehensive_token_check(access_token, drive_id):
    """完整的 token 和權限檢查"""

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    print("=" * 60)
    print("🔐 Microsoft Graph API 權限診斷工具")
    print("=" * 60)

    # 1. 解析 Token
    print("\n【1】解析 Access Token")
    print("-" * 60)
    try:
        token_parts = access_token.split(".")
        if len(token_parts) >= 2:
            payload = token_parts[1]
            # 補齊 base64 padding
            payload += "=" * (4 - len(payload) % 4)
            decoded_bytes = base64.urlsafe_b64decode(payload)
            token_data = json.loads(decoded_bytes)

            print(f"✓ App ID (aud): {token_data.get('aud', 'N/A')}")
            print(f"✓ 發行者 (iss): {token_data.get('iss', 'N/A')}")
            print(f"✓ 租戶 ID (tid): {token_data.get('tid', 'N/A')}")

            # 檢查過期時間
            exp = token_data.get("exp")
            if exp:
                exp_time = datetime.fromtimestamp(exp)
                now = datetime.now()
                if exp_time > now:
                    remaining = exp_time - now
                    hours = remaining.total_seconds() / 3600
                    print(f"✓ Token 有效期限: {exp_time} (剩餘 {hours:.1f} 小時)")
                else:
                    print(f"❌ Token 已過期: {exp_time}")
                    print("   請重新取得 Token!")
                    return False

            # 檢查權限範圍
            roles = token_data.get("roles", [])
            scp = token_data.get("scp", "")

            if roles:
                print(f"\n✓ Application Permissions (roles):")
                for role in roles:
                    print(f"   - {role}")

                # 檢查必要權限
                required_permissions = [
                    "Sites.Read.All",
                    "Sites.ReadWrite.All",
                    "Files.Read.All",
                    "Files.ReadWrite.All",
                ]
                has_required = any(perm in roles for perm in required_permissions)
                if not has_required:
                    print(f"\n⚠️  警告: 缺少必要的 Sites 或 Files 權限!")

            elif scp:
                print(f"\n✓ Delegated Permissions (scp): {scp}")
            else:
                print("\n⚠️  警告: 找不到權限資訊!")

            # 只在需要時顯示完整 payload (避免輸出過長)
            # print(f"\n完整 Token Payload:")
            # print(json.dumps(token_data, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"❌ Token 解析失敗: {e}")
        return False

    # 2. 測試基本 API 存取
    print("\n\n【2】測試 API 端點存取")
    print("-" * 60)

    test_endpoints = [
        ("列出所有 Sites", "https://graph.microsoft.com/v1.0/sites", True),
        ("列出所有 Drives", "https://graph.microsoft.com/v1.0/drives", True),
        ("取得 Root Site", "https://graph.microsoft.com/v1.0/sites/root", False),
        ("取得特定 Drive", f"https://graph.microsoft.com/v1.0/drives/{drive_id}", True),
        (
            "Drive Root Children",
            f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children",
            True,
        ),
        (
            "Drive 搜尋",
            f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/search(q='')",
            True,
        ),
    ]

    results = {}  # 儲存測試結果供後續分析

    for name, url, show_detail in test_endpoints:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            results[name] = {
                "status": response.status_code,
                "success": response.status_code == 200,
            }

            if response.status_code == 200:
                data = response.json()
                count = len(data.get("value", [])) if "value" in data else "N/A"
                results[name]["count"] = count if isinstance(count, int) else 0

                print(f"✅ {name}: 成功 (項目數: {count})")

                if show_detail and "value" in data and data["value"]:
                    print(f"   前3筆資料:")
                    for item in data["value"][:3]:
                        item_name = item.get("name", item.get("displayName", "N/A"))
                        item_type = (
                            "📁"
                            if "folder" in item
                            else "📄" if "file" in item else "📋"
                        )
                        print(f"   {item_type} {item_name}")

            elif response.status_code == 401:
                print(f"❌ {name}: 認證失敗 (401) - Token 可能無效或過期")
            elif response.status_code == 403:
                print(f"❌ {name}: 權限不足 (403)")
                error_msg = response.json().get("error", {}).get("message", "")
                print(f"   錯誤訊息: {error_msg}")
            elif response.status_code == 404:
                print(f"⚠️  {name}: 找不到資源 (404)")
            else:
                print(f"❌ {name}: 失敗 ({response.status_code})")
                try:
                    error_data = response.json()
                    print(
                        f"   錯誤: {error_data.get('error', {}).get('message', 'Unknown')}"
                    )
                except:
                    print(f"   回應: {response.text[:200]}")

        except requests.exceptions.Timeout:
            print(f"⏱️  {name}: 請求逾時")
            results[name] = {"status": "timeout", "success": False}
        except Exception as e:
            print(f"❌ {name}: 異常 - {str(e)}")
            results[name] = {"status": "error", "success": False}

    # 3. 詳細檢查 Drive
    print("\n\n【3】詳細檢查目標 Drive")
    print("-" * 60)

    drive_has_content = False

    try:
        drive_response = requests.get(
            f"https://graph.microsoft.com/v1.0/drives/{drive_id}", headers=headers
        )

        if drive_response.status_code == 200:
            drive_data = drive_response.json()
            print(f"✓ Drive 名稱: {drive_data.get('name')}")
            print(f"✓ Drive 類型: {drive_data.get('driveType')}")
            print(f"✓ WebUrl: {drive_data.get('webUrl')}")

            owner = drive_data.get("owner", {})
            owner_name = owner.get("user", {}).get("displayName") or owner.get(
                "group", {}
            ).get("displayName", "N/A")
            print(f"✓ 擁有者: {owner_name}")

            # 檢查 quota
            quota = drive_data.get("quota", {})
            used = quota.get("used", 0)
            total = quota.get("total", 0)

            if used > 0:
                drive_has_content = True
                used_mb = used / (1024 * 1024)
                print(f"\n✓ 使用空間: {used:,} bytes ({used_mb:.2f} MB)")
                if total > 0:
                    print(f"✓ 總空間: {total:,} bytes ({used/total*100:.2f}%)")
                print(f"\n⚠️  重要: Drive 有 {used_mb:.2f} MB 使用量,但 API 看不到內容!")
                print(f"   這強烈暗示 SharePoint 網站權限問題!")
            else:
                print(f"\n✓ 使用空間: 0 bytes (Drive 可能真的是空的)")

            # 如果有 sharePointIds
            if "sharePointIds" in drive_data:
                sp_ids = drive_data["sharePointIds"]
                print(f"\n✓ SharePoint 資訊:")
                site_id = sp_ids.get("siteId", "N/A")
                print(f"   - Site ID: {site_id}")
                print(f"   - Web ID: {sp_ids.get('webId', 'N/A')}")
                print(f"   - List ID: {sp_ids.get('listId', 'N/A')}")

                # 嘗試存取對應的 Site
                if site_id and site_id != "N/A":
                    print(f"\n嘗試存取對應的 SharePoint Site...")
                    site_response = requests.get(
                        f"https://graph.microsoft.com/v1.0/sites/{site_id}",
                        headers=headers,
                    )
                    if site_response.status_code == 200:
                        site_data = site_response.json()
                        print(f"✅ 可以存取 Site: {site_data.get('displayName')}")
                    else:
                        print(f"❌ 無法存取 Site (狀態碼: {site_response.status_code})")
                        print(f"   這可能表示缺少 Site 層級的權限!")

        else:
            print(f"❌ 無法取得 Drive 資訊 (狀態碼: {drive_response.status_code})")

    except Exception as e:
        print(f"❌ Drive 檢查失敗: {e}")

    # 4. 智能診斷分析
    print("\n\n【4】智能診斷分析")
    print("-" * 60)

    # 分析測試結果
    can_list_drives = results.get("列出所有 Drives", {}).get("success", False)
    can_get_drive = results.get("取得特定 Drive", {}).get("success", False)
    children_count = results.get("Drive Root Children", {}).get("count", -1)
    search_count = results.get("Drive 搜尋", {}).get("count", -1)

    print("\n📊 診斷結果:")

    if (
        can_list_drives
        and can_get_drive
        and children_count == 0
        and search_count == 0
        and drive_has_content
    ):
        print("\n🎯 診斷結論: **SharePoint 網站層級權限不足** (信心度: 95%+)")
        print("\n證據:")
        print("  ✅ Azure AD 權限正常 (可列出 Drives)")
        print("  ✅ 可取得 Drive 詳細資訊")
        print(f"  ✅ Drive 有內容 (使用量 > 0)")
        print("  ❌ 但看不到任何檔案或資料夾")
        print("  ❌ 搜尋也找不到任何內容")

        print("\n💡 解決方案:")
        print("  請客戶的 SharePoint 管理員執行以下步驟:")
        print("  1. 前往 SharePoint 網站設定")
        print("  2. 點擊「網站權限」")
        print("  3. 授與應用程式「讀取」權限")
        print(f"  4. 應用程式識別: 從 Token 中的 app_displayname 或 appid")

    elif (
        can_list_drives
        and can_get_drive
        and children_count == 0
        and not drive_has_content
    ):
        print("\n🤔 診斷結論: Drive 可能真的是空的")
        print("\n建議:")
        print("  1. 請客戶確認測試檔案是否已上傳")
        print("  2. 確認檔案位置是否正確")

    elif not can_list_drives:
        print("\n❌ 診斷結論: Azure AD 權限不足")
        print("\n解決方案:")
        print("  1. 確認應用程式已設定 Sites.Read.All 或 Files.Read.All")
        print("  2. 確認已執行 Admin Consent (管理員同意)")

    else:
        print("\n⚠️  診斷結論: 需要更多資訊")
        print("  請檢查上述測試結果中的錯誤訊息")

    print("\n" + "=" * 60)
    print("檢查完成!")
    print("=" * 60)

    return True


# ============================================
# 使用方式
# ============================================
if __name__ == "__main__":
    # 在這裡填入你的資訊
    ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJub25jZSI6IkFqYnc5U3JNVHBqQ3lNcGZBYkl6ZnNtYl9zQXFpRUNzN09hY3l1cklHaWsiLCJhbGciOiJSUzI1NiIsIng1dCI6InJ0c0ZULWItN0x1WTdEVlllU05LY0lKN1ZuYyIsImtpZCI6InJ0c0ZULWItN0x1WTdEVlllU05LY0lKN1ZuYyJ9.eyJhdWQiOiJodHRwczovL2dyYXBoLm1pY3Jvc29mdC5jb20iLCJpc3MiOiJodHRwczovL3N0cy53aW5kb3dzLm5ldC9hNTA4M2Y3My0xMDlkLTRmMjktOGExZi1lMzYyNDEzOTkxODYvIiwiaWF0IjoxNzY2NTQ2NDY2LCJuYmYiOjE3NjY1NDY0NjYsImV4cCI6MTc2NjU1MDM2NiwiYWlvIjoiazJKZ1lEaHlnV3R4M3JYVmM3WmMxWjhRYTFlMEhBQT0iLCJhcHBfZGlzcGxheW5hbWUiOiJPbmVEcml2ZS1BUEktRm9yLU9kb29CMkIiLCJhcHBpZCI6IjI0ODQ3MjY1LWY0ZTMtNGJkNS1iYjc1LTYzYmE4ZGVkOGQ5MyIsImFwcGlkYWNyIjoiMSIsImlkcCI6Imh0dHBzOi8vc3RzLndpbmRvd3MubmV0L2E1MDgzZjczLTEwOWQtNGYyOS04YTFmLWUzNjI0MTM5OTE4Ni8iLCJpZHR5cCI6ImFwcCIsIm9pZCI6ImFjNDZlNDE4LTI3NTctNGRjYy04N2M5LWFlYzEyN2ViOTQ1NCIsInJoIjoiMS5BVllBY3o4SXBaMFFLVS1LSC1OaVFUbVJoZ01BQUFBQUFBQUF3QUFBQUFBQUFBQWlBUUJXQUEuIiwicm9sZXMiOlsiU2l0ZXMuUmVhZFdyaXRlLkFsbCIsIkZpbGVzLlJlYWRXcml0ZS5BbGwiLCJGaWxlcy5SZWFkLkFsbCJdLCJzdWIiOiJhYzQ2ZTQxOC0yNzU3LTRkY2MtODdjOS1hZWMxMjdlYjk0NTQiLCJ0ZW5hbnRfcmVnaW9uX3Njb3BlIjoiQVMiLCJ0aWQiOiJhNTA4M2Y3My0xMDlkLTRmMjktOGExZi1lMzYyNDEzOTkxODYiLCJ1dGkiOiJJZjhDYlloeThVLXFjQ3oxTHBzR0FBIiwidmVyIjoiMS4wIiwid2lkcyI6WyIwOTk3YTFkMC0wZDFkLTRhY2ItYjQwOC1kNWNhNzMxMjFlOTAiXSwieG1zX2FjZCI6MTc2NTUzNjEzMywieG1zX2FjdF9mY3QiOiIzIDkiLCJ4bXNfZnRkIjoiaFJQSnpnUTBQRGhpRHp6NERJYnRkbnB1eHZCTm9FbVo4VmZoaFMtcmxrVUJhbUZ3WVc1bFlYTjBMV1J6YlhNIiwieG1zX2lkcmVsIjoiMjQgNyIsInhtc19yZCI6IjAuNDJMbFlCSmlEQk1TNFdBWEVyQm5ObWRfZmlIWXIyOXhYdm9scVdQLVFGRk9JUUhCOEF1NlBEeDlfcE1DTnBrOG12MklBU2pLSVNUQXpBQUJCNkEwQUEiLCJ4bXNfc3ViX2ZjdCI6IjkgMyIsInhtc190Y2R0IjoxNDc5MzU0NzQ1LCJ4bXNfdG50X2ZjdCI6IjMgNCJ9.PcB2Zbk5kPexDAwGOj8rpBfB1q06KdilrfplLn2NXqM4vYFKCFTeZh3-SLUTG7d7QqCTm9I_wvYB_FeVMWziY7c3d3ldy8YgPN__UL3XG_E_VqxLSSxMiw2WzqWhSFCY-46u44SbDcr_x6KX77TJf7Mt7gmorJRMOKeGGdTljAZXyzy9lhF_QudIP1NiitjYRUWtdwB40PzVZcWz0SPMZseODSkVU2Fik3_vnfZgsrwhbggSNhpbVvKTX-xy10RiqZcBUodB0vRkxDXsvP1K8odVFJ-VjtfsY_3texzZLz5Ovf8YxEgiAuQlIsGN1mJOusDtMoqZyHJDLbhc8ugbIw"  # 貼在這裡
    DRIVE_ID = "b!zb72HouSvkqZpRtHXR_pWq093KJoXRtFuAg-fs5xFQTzF8oemXwWQ6XKOad1W-Co"  # 貼在這裡

    comprehensive_token_check(ACCESS_TOKEN, DRIVE_ID)
