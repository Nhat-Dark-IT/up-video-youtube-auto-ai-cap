from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(
    'client_secret_606032748089-3fkpfi3tg094atrhp3b92nd8cda8623c.apps.googleusercontent.com.json',
    scopes=['https://www.googleapis.com/auth/youtube.upload']
)

credentials = flow.run_local_server(port=8080)

print(f"Access Token: {credentials.token}")
print(f"Refresh Token: {credentials.refresh_token}")
