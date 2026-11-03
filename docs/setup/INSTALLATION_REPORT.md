# PROMPT 1 — Kurulum ve doğrulama raporu

Ortam: Debian GNU/Linux 13 (trixie, 13.7), x86_64; Python 3.13.16; proje sanal ortamı `.venv`; IDE: yok, workspace araçları ve bash kullanıldı.

İstenen eski bağımlılık listesi `docs/setup/requirements.requested.txt` içinde korunmuştur. Bu listeyle yapılan gerçek kurulum Pillow 10.0.0 build hazırlığında `KeyError: '__version__'` vererek başarısız oldu (exit 1). Diğer eski pinlerin kurulumu bu girişimde doğrulanmamıştır. Etkin liste, Python 3.13 uyumu için değiştirilmiş ve kurulum başarılı olmuştur; `asyncio` Python standart kütüphanesinde bulunduğu için ayrı backport kaldırılmıştır. MoviePy 2.2.1 API'si 1.x'ten farklıdır. Ayrıntı: `docs/setup/DEPENDENCY_DECISIONS.md`.

Chromium indirmesi başarılı olsa da ilk yerel test `libnspr4.so` eksikliğiyle başarısız oldu (`setup_reports/07-validation.log`). Playwright sistem bağımlılıkları kuruldu (`setup_reports/10-playwright-system-deps.log`, exit 0); aynı test tekrar başarılı oldu. Son doğrulama: 7/7 test geçti, `pip check` temiz, yerel ortam kontrolü başarılı. Harici API çağrısı veya OAuth gerçekleştirilmedi.

Ağaç görünümü `.venv`, `.git`, `__pycache__` ve `.pyc` dosyalarını dışlar; bu dizinler/file'lar dahil eksiksiz ortam dökümü değildir. Sanal ortam ve Playwright'ın tarayıcı önbelleği çalışma alanı kalıcı anlık görüntüsüne dahil edilmediğinden başka bir oturumda/ortamda README'deki yeniden kurulum gerekebilir.

## Kaynak günlükleri

- Playwright Chromium kurulumu: `setup_reports/05-playwright-install.log` (exit 0).
- FFmpeg/tree apt kurulumu: `setup_reports/02-apt-tools.log` (exit 0).
- İlk başarısız doğrulama: `setup_reports/07-validation.log`.
- Playwright sistem bağımlılıkları: `setup_reports/10-playwright-system-deps.log` (exit 0).
- Kilitli paketler: `requirements.lock.txt`.

Aşağıdaki komut çıktıları kısaltılmadan orijinal loglardan alınmıştır.

## Etkin requirements.txt — tam içerik

```text
google-api-python-client==2.201.0
google-auth-oauthlib==1.5.0
google-auth-httplib2==0.4.4
edge-tts==7.3.1
moviepy==2.2.1
ffmpeg-python==0.2.0
opencv-python==4.14.0.94
Pillow==11.3.0
playwright==1.64.1
selenium==4.52.0
pydrive2==1.21.3
python-dotenv==1.2.4
aiohttp==3.14.5
requests==2.34.2
beautifulsoup4==4.15.0
yt-dlp==2026.10.26
```

## İlk, istenen pinlerle pip kurulumu — tam çıktı, exit 1

```text
Collecting google-api-python-client==2.70.0 (from -r requirements.txt (line 1))
  Downloading google_api_python_client-2.70.0-py2.py3-none-any.whl.metadata (6.6 kB)
Collecting google-auth-oauthlib==0.4.6 (from -r requirements.txt (line 2))
  Downloading google_auth_oauthlib-0.4.6-py2.py3-none-any.whl.metadata (2.7 kB)
Collecting google-auth-httplib2==0.1.0 (from -r requirements.txt (line 3))
  Downloading google_auth_httplib2-0.1.0-py2.py3-none-any.whl.metadata (2.1 kB)
Collecting edge-tts==6.1.9 (from -r requirements.txt (line 4))
  Downloading edge_tts-6.1.9-py3-none-any.whl.metadata (4.3 kB)
Collecting moviepy==1.0.3 (from -r requirements.txt (line 5))
  Downloading moviepy-1.0.3.tar.gz (388 kB)
  Installing build dependencies: started
  Installing build dependencies: finished with status 'done'
  Getting requirements to build wheel: started
  Getting requirements to build wheel: finished with status 'done'
  Preparing metadata (pyproject.toml): started
  Preparing metadata (pyproject.toml): finished with status 'done'
Collecting ffmpeg-python==0.2.0 (from -r requirements.txt (line 6))
  Downloading ffmpeg_python-0.2.0-py3-none-any.whl.metadata (1.7 kB)
Collecting opencv-python==4.8.0.74 (from -r requirements.txt (line 7))
  Downloading opencv_python-4.8.0.74-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (19 kB)
Collecting Pillow==10.0.0 (from -r requirements.txt (line 8))
  Downloading Pillow-10.0.0.tar.gz (50.5 MB)
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 50.5/50.5 MB 156.5 MB/s  0:00:00
  Installing build dependencies: started
  Installing build dependencies: finished with status 'done'
  Getting requirements to build wheel: started
  Getting requirements to build wheel: finished with status 'error'
  error: subprocess-exited-with-error
  
  × Getting requirements to build wheel did not run successfully.
  │ exit code: 1
  ╰─> [21 lines of output]
      Traceback (most recent call last):
        File "/home/user/youtube_shorts_automation/.venv/lib/python3.13/site-packages/pip/_vendor/pyproject_hooks/_in_process/_in_process.py", line 389, in <module>
          main()
          ~~~~^^
        File "/home/user/youtube_shorts_automation/.venv/lib/python3.13/site-packages/pip/_vendor/pyproject_hooks/_in_process/_in_process.py", line 373, in main
          json_out["return_val"] = hook(**hook_input["kwargs"])
                                   ~~~~^^^^^^^^^^^^^^^^^^^^^^^^
        File "/home/user/youtube_shorts_automation/.venv/lib/python3.13/site-packages/pip/_vendor/pyproject_hooks/_in_process/_in_process.py", line 143, in get_requires_for_build_wheel
          return hook(config_settings)
        File "/tmp/pip-build-env-gelwaque/overlay/lib/python3.13/site-packages/setuptools/build_meta.py", line 333, in get_requires_for_build_wheel
          return self._get_build_requires(config_settings, requirements=[])
                 ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        File "/tmp/pip-build-env-gelwaque/overlay/lib/python3.13/site-packages/setuptools/build_meta.py", line 301, in _get_build_requires
          self.run_setup()
          ~~~~~~~~~~~~~~^^
        File "/tmp/pip-build-env-gelwaque/overlay/lib/python3.13/site-packages/setuptools/build_meta.py", line 317, in run_setup
          exec(code, locals())  # noqa: S102 # exec is intentional here
          ~~~~^^^^^^^^^^^^^^^^
        File "<string>", line 30, in <module>
        File "<string>", line 27, in get_version
      KeyError: '__version__'
      [end of output]
  
  note: This error originates from a subprocess, and is likely not a problem with pip.

[notice] A new release of pip is available: 26.2.1 -> 26.3
[notice] To update, run: /home/user/youtube_shorts_automation/.venv/bin/python -m pip install --upgrade pip
ERROR: Failed to build 'Pillow' when getting requirements to build wheel

PIP_EXIT_CODE=1
```

## Uyumlu pinlerle pip kurulumu — tam çıktı, exit 0

```text
Collecting google-api-python-client==2.201.0 (from -r requirements.txt (line 1))
  Downloading google_api_python_client-2.201.0-py3-none-any.whl.metadata (6.8 kB)
Collecting google-auth-oauthlib==1.5.0 (from -r requirements.txt (line 2))
  Downloading google_auth_oauthlib-1.5.0-py3-none-any.whl.metadata (2.6 kB)
Collecting google-auth-httplib2==0.4.4 (from -r requirements.txt (line 3))
  Downloading google_auth_httplib2-0.4.4-py3-none-any.whl.metadata (3.0 kB)
Collecting edge-tts==7.3.1 (from -r requirements.txt (line 4))
  Downloading edge_tts-7.3.1-py3-none-any.whl.metadata (6.1 kB)
Collecting moviepy==2.2.1 (from -r requirements.txt (line 5))
  Downloading moviepy-2.2.1-py3-none-any.whl.metadata (6.9 kB)
Collecting ffmpeg-python==0.2.0 (from -r requirements.txt (line 6))
  Using cached ffmpeg_python-0.2.0-py3-none-any.whl.metadata (1.7 kB)
Collecting opencv-python==4.14.0.94 (from -r requirements.txt (line 7))
  Downloading opencv_python-4.14.0.94-cp37-abi3-manylinux_2_28_x86_64.whl.metadata (19 kB)
Collecting Pillow==11.3.0 (from -r requirements.txt (line 8))
  Downloading pillow-11.3.0-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl.metadata (9.0 kB)
Collecting playwright==1.64.1 (from -r requirements.txt (line 9))
  Downloading playwright-1.64.1-py3-none-manylinux1_x86_64.whl.metadata (3.3 kB)
Collecting selenium==4.52.0 (from -r requirements.txt (line 10))
  Downloading selenium-4.52.0-py3-none-any.whl.metadata (7.5 kB)
Collecting pydrive2==1.21.3 (from -r requirements.txt (line 11))
  Downloading PyDrive2-1.21.3-py3-none-any.whl.metadata (7.0 kB)
Collecting python-dotenv==1.2.4 (from -r requirements.txt (line 12))
  Downloading python_dotenv-1.2.4-py3-none-any.whl.metadata (29 kB)
Collecting aiohttp==3.14.5 (from -r requirements.txt (line 13))
  Downloading aiohttp-3.14.5-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (8.3 kB)
Collecting requests==2.34.2 (from -r requirements.txt (line 14))
  Downloading requests-2.34.2-py3-none-any.whl.metadata (4.8 kB)
Collecting beautifulsoup4==4.15.0 (from -r requirements.txt (line 15))
  Downloading beautifulsoup4-4.15.0-py3-none-any.whl.metadata (3.8 kB)
Collecting yt-dlp==2026.10.26 (from -r requirements.txt (line 16))
  Downloading yt_dlp-2026.10.26-py3-none-any.whl.metadata (183 kB)
Collecting httplib2<1.0.0,>=0.19.0 (from google-api-python-client==2.201.0->-r requirements.txt (line 1))
  Downloading httplib2-0.32.1-py3-none-any.whl.metadata (2.2 kB)
Collecting google-auth!=2.24.0,!=2.25.0,<3.0.0,>=1.32.0 (from google-api-python-client==2.201.0->-r requirements.txt (line 1))
  Downloading google_auth-2.62.1-py3-none-any.whl.metadata (6.0 kB)
Collecting google-api-core!=2.0.*,!=2.1.*,!=2.2.*,!=2.3.0,<3.0.0,>=1.31.5 (from google-api-python-client==2.201.0->-r requirements.txt (line 1))
  Downloading google_api_core-2.43.2-py3-none-any.whl.metadata (3.2 kB)
Collecting uritemplate<5,>=3.0.1 (from google-api-python-client==2.201.0->-r requirements.txt (line 1))
  Downloading uritemplate-4.2.0-py3-none-any.whl.metadata (2.6 kB)
Collecting requests-oauthlib>=0.7.0 (from google-auth-oauthlib==1.5.0->-r requirements.txt (line 2))
  Downloading requests_oauthlib-2.0.0-py2.py3-none-any.whl.metadata (11 kB)
Collecting certifi>=2023.11.17 (from edge-tts==7.3.1->-r requirements.txt (line 4))
  Downloading certifi-2026.10.23-py3-none-any.whl.metadata (2.5 kB)
Collecting tabulate<1.0.0,>=0.4.4 (from edge-tts==7.3.1->-r requirements.txt (line 4))
  Downloading tabulate-0.10.0-py3-none-any.whl.metadata (40 kB)
Collecting typing-extensions<5.0.0,>=4.1.0 (from edge-tts==7.3.1->-r requirements.txt (line 4))
  Downloading typing_extensions-4.16.0-py3-none-any.whl.metadata (3.3 kB)
Collecting aiohappyeyeballs>=2.5.0 (from aiohttp==3.14.5->-r requirements.txt (line 13))
  Downloading aiohappyeyeballs-2.7.1-py3-none-any.whl.metadata (5.9 kB)
Collecting aiosignal>=1.4.0 (from aiohttp==3.14.5->-r requirements.txt (line 13))
  Downloading aiosignal-1.4.0-py3-none-any.whl.metadata (3.7 kB)
Collecting attrs>=17.3.0 (from aiohttp==3.14.5->-r requirements.txt (line 13))
  Downloading attrs-26.1.0-py3-none-any.whl.metadata (8.8 kB)
Collecting frozenlist>=1.1.1 (from aiohttp==3.14.5->-r requirements.txt (line 13))
  Downloading frozenlist-1.8.0-cp313-cp313-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl.metadata (20 kB)
Collecting multidict<8.0,>=4.5 (from aiohttp==3.14.5->-r requirements.txt (line 13))
  Downloading multidict-7.2.1-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (6.1 kB)
Collecting propcache>=0.2.0 (from aiohttp==3.14.5->-r requirements.txt (line 13))
  Downloading propcache-0.5.4-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (25 kB)
Collecting yarl<2.0,>=1.25.1 (from aiohttp==3.14.5->-r requirements.txt (line 13))
  Downloading yarl-1.25.1-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (111 kB)
Collecting decorator<6.0,>=4.0.2 (from moviepy==2.2.1->-r requirements.txt (line 5))
  Downloading decorator-5.3.1-py3-none-any.whl.metadata (3.9 kB)
Collecting imageio<3.0,>=2.5 (from moviepy==2.2.1->-r requirements.txt (line 5))
  Downloading imageio-2.38.1-py3-none-any.whl.metadata (9.7 kB)
Collecting imageio_ffmpeg>=0.2.0 (from moviepy==2.2.1->-r requirements.txt (line 5))
  Downloading imageio_ffmpeg-0.8.0-py3-none-manylinux_2_28_x86_64.whl.metadata (1.5 kB)
Collecting numpy>=1.25.0 (from moviepy==2.2.1->-r requirements.txt (line 5))
  Downloading numpy-2.5.4-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl.metadata (6.6 kB)
Collecting proglog<=1.0.0 (from moviepy==2.2.1->-r requirements.txt (line 5))
  Downloading proglog-0.1.12-py3-none-any.whl.metadata (794 bytes)
Collecting future (from ffmpeg-python==0.2.0->-r requirements.txt (line 6))
  Downloading future-1.0.0-py3-none-any.whl.metadata (4.0 kB)
Collecting pyee<15,>=13 (from playwright==1.64.1->-r requirements.txt (line 9))
  Downloading pyee-14.0.0-py3-none-any.whl.metadata (1.8 kB)
Collecting greenlet<4.0.0,>=3.1.1 (from playwright==1.64.1->-r requirements.txt (line 9))
  Downloading greenlet-3.5.6-cp313-cp313-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl.metadata (3.8 kB)
Collecting trio<1.0,>=0.31.0 (from selenium==4.52.0->-r requirements.txt (line 10))
  Downloading trio-0.35.0-py3-none-any.whl.metadata (8.5 kB)
Collecting trio-websocket<1.0,>=0.12.2 (from selenium==4.52.0->-r requirements.txt (line 10))
  Downloading trio_websocket-0.12.2-py3-none-any.whl.metadata (5.1 kB)
Collecting urllib3<3.0,>=2.6.3 (from urllib3[socks]<3.0,>=2.6.3->selenium==4.52.0->-r requirements.txt (line 10))
  Downloading urllib3-2.8.0-py3-none-any.whl.metadata (7.4 kB)
Collecting websocket-client<2.0,>=1.8.0 (from selenium==4.52.0->-r requirements.txt (line 10))
  Downloading websocket_client-1.9.2-py3-none-any.whl.metadata (8.3 kB)
Collecting oauth2client>=4.0.0 (from pydrive2==1.21.3->-r requirements.txt (line 11))
  Downloading oauth2client-4.1.3-py2.py3-none-any.whl.metadata (1.2 kB)
Collecting PyYAML>=3.0 (from pydrive2==1.21.3->-r requirements.txt (line 11))
  Downloading pyyaml-6.0.3-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (2.4 kB)
Collecting cryptography<44 (from pydrive2==1.21.3->-r requirements.txt (line 11))
  Downloading cryptography-43.0.3-cp39-abi3-manylinux_2_28_x86_64.whl.metadata (5.4 kB)
Collecting pyOpenSSL<=24.2.1,>=19.1.0 (from pydrive2==1.21.3->-r requirements.txt (line 11))
  Downloading pyOpenSSL-24.2.1-py3-none-any.whl.metadata (13 kB)
Collecting charset_normalizer<4,>=2 (from requests==2.34.2->-r requirements.txt (line 14))
  Downloading charset_normalizer-3.5.2-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (46 kB)
Collecting idna<4,>=2.5 (from requests==2.34.2->-r requirements.txt (line 14))
  Downloading idna-3.20-py3-none-any.whl.metadata (7.2 kB)
Collecting soupsieve>=1.6.1 (from beautifulsoup4==4.15.0->-r requirements.txt (line 15))
  Downloading soupsieve-3.0.4-py3-none-any.whl.metadata (4.4 kB)
Collecting cffi>=1.12 (from cryptography<44->pydrive2==1.21.3->-r requirements.txt (line 11))
  Downloading cffi-2.1.1-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl.metadata (2.5 kB)
Collecting googleapis-common-protos<2.0.0,>=1.69.2 (from google-api-core!=2.0.*,!=2.1.*,!=2.2.*,!=2.3.0,<3.0.0,>=1.31.5->google-api-python-client==2.201.0->-r requirements.txt (line 1))
  Downloading googleapis_common_protos-1.76.0-py3-none-any.whl.metadata (8.5 kB)
Collecting protobuf<8.0.0,>=6.33.5 (from google-api-core!=2.0.*,!=2.1.*,!=2.2.*,!=2.3.0,<3.0.0,>=1.31.5->google-api-python-client==2.201.0->-r requirements.txt (line 1))
  Downloading protobuf-7.36.2-cp310-abi3-manylinux2014_x86_64.whl.metadata (595 bytes)
Collecting proto-plus<2.0.0,>=1.26.1 (from google-api-core!=2.0.*,!=2.1.*,!=2.2.*,!=2.3.0,<3.0.0,>=1.31.5->google-api-python-client==2.201.0->-r requirements.txt (line 1))
  Downloading proto_plus-1.29.0-py3-none-any.whl.metadata (2.2 kB)
Collecting opentelemetry-api<2.0.0,>=1.44.0 (from google-api-core!=2.0.*,!=2.1.*,!=2.2.*,!=2.3.0,<3.0.0,>=1.31.5->google-api-python-client==2.201.0->-r requirements.txt (line 1))
  Downloading opentelemetry_api-1.45.2-py3-none-any.whl.metadata (1.4 kB)
Collecting pyasn1-modules>=0.2.1 (from google-auth!=2.24.0,!=2.25.0,<3.0.0,>=1.32.0->google-api-python-client==2.201.0->-r requirements.txt (line 1))
  Downloading pyasn1_modules-0.4.2-py3-none-any.whl.metadata (3.5 kB)
Collecting pyparsing<4,>=3.1 (from httplib2<1.0.0,>=0.19.0->google-api-python-client==2.201.0->-r requirements.txt (line 1))
  Downloading pyparsing-3.3.3-py3-none-any.whl.metadata (5.9 kB)
Collecting tqdm (from proglog<=1.0.0->moviepy==2.2.1->-r requirements.txt (line 5))
  Downloading tqdm-4.70.1-py3-none-any.whl.metadata (57 kB)
Collecting sortedcontainers (from trio<1.0,>=0.31.0->selenium==4.52.0->-r requirements.txt (line 10))
  Downloading sortedcontainers-2.4.0-py2.py3-none-any.whl.metadata (10 kB)
Collecting outcome (from trio<1.0,>=0.31.0->selenium==4.52.0->-r requirements.txt (line 10))
  Downloading outcome-1.3.0.post0-py2.py3-none-any.whl.metadata (2.6 kB)
Collecting sniffio>=1.3.0 (from trio<1.0,>=0.31.0->selenium==4.52.0->-r requirements.txt (line 10))
  Downloading sniffio-1.3.1-py3-none-any.whl.metadata (3.9 kB)
Collecting wsproto>=0.14 (from trio-websocket<1.0,>=0.12.2->selenium==4.52.0->-r requirements.txt (line 10))
  Downloading wsproto-1.3.2-py3-none-any.whl.metadata (5.2 kB)
Collecting pysocks!=1.5.7,<2.0,>=1.5.6 (from urllib3[socks]<3.0,>=2.6.3->selenium==4.52.0->-r requirements.txt (line 10))
  Downloading PySocks-1.7.1-py3-none-any.whl.metadata (13 kB)
Collecting pycparser (from cffi>=1.12->cryptography<44->pydrive2==1.21.3->-r requirements.txt (line 11))
  Downloading pycparser-3.12-py3-none-any.whl.metadata (9.7 kB)
Collecting pyasn1>=0.1.7 (from oauth2client>=4.0.0->pydrive2==1.21.3->-r requirements.txt (line 11))
  Downloading pyasn1-0.6.5-py3-none-any.whl.metadata (8.4 kB)
Collecting rsa>=3.1.4 (from oauth2client>=4.0.0->pydrive2==1.21.3->-r requirements.txt (line 11))
  Downloading rsa-4.9.1-py3-none-any.whl.metadata (5.6 kB)
Collecting six>=1.6.1 (from oauth2client>=4.0.0->pydrive2==1.21.3->-r requirements.txt (line 11))
  Downloading six-1.17.0-py2.py3-none-any.whl.metadata (1.7 kB)
Collecting oauthlib>=3.0.0 (from requests-oauthlib>=0.7.0->google-auth-oauthlib==1.5.0->-r requirements.txt (line 2))
  Downloading oauthlib-4.0.1-py3-none-any.whl.metadata (8.6 kB)
Collecting h11<1,>=0.16.0 (from wsproto>=0.14->trio-websocket<1.0,>=0.12.2->selenium==4.52.0->-r requirements.txt (line 10))
  Downloading h11-0.16.0-py3-none-any.whl.metadata (8.3 kB)
Downloading google_api_python_client-2.201.0-py3-none-any.whl (16.8 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 16.8/16.8 MB 152.4 MB/s  0:00:00
Downloading google_auth_httplib2-0.4.4-py3-none-any.whl (9.5 kB)
Downloading google_auth_oauthlib-1.5.0-py3-none-any.whl (20 kB)
Downloading edge_tts-7.3.1-py3-none-any.whl (38 kB)
Downloading aiohttp-3.14.5-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (1.9 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.9/1.9 MB 143.5 MB/s  0:00:00
Downloading moviepy-2.2.1-py3-none-any.whl (129 kB)
Downloading pillow-11.3.0-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl (6.6 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 6.6/6.6 MB 198.2 MB/s  0:00:00
Downloading ffmpeg_python-0.2.0-py3-none-any.whl (25 kB)
Downloading opencv_python-4.14.0.94-cp37-abi3-manylinux_2_28_x86_64.whl (77.4 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 77.4/77.4 MB 103.9 MB/s  0:00:00
Downloading playwright-1.64.1-py3-none-manylinux1_x86_64.whl (48.5 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 48.5/48.5 MB 128.7 MB/s  0:00:00
Downloading selenium-4.52.0-py3-none-any.whl (12.1 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 12.1/12.1 MB 139.4 MB/s  0:00:00
Downloading PyDrive2-1.21.3-py3-none-any.whl (47 kB)
Downloading python_dotenv-1.2.4-py3-none-any.whl (23 kB)
Downloading requests-2.34.2-py3-none-any.whl (73 kB)
Downloading beautifulsoup4-4.15.0-py3-none-any.whl (109 kB)
Downloading yt_dlp-2026.10.26-py3-none-any.whl (3.2 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 3.2/3.2 MB 160.7 MB/s  0:00:00
Downloading charset_normalizer-3.5.2-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (254 kB)
Downloading cryptography-43.0.3-cp39-abi3-manylinux_2_28_x86_64.whl (4.0 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 4.0/4.0 MB 142.1 MB/s  0:00:00
Downloading decorator-5.3.1-py3-none-any.whl (10 kB)
Downloading google_api_core-2.43.2-py3-none-any.whl (224 kB)
Downloading google_auth-2.62.1-py3-none-any.whl (267 kB)
Downloading googleapis_common_protos-1.76.0-py3-none-any.whl (307 kB)
Downloading greenlet-3.5.6-cp313-cp313-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl (623 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 623.8/623.8 kB 99.1 MB/s  0:00:00
Downloading httplib2-0.32.1-py3-none-any.whl (92 kB)
Downloading idna-3.20-py3-none-any.whl (69 kB)
Downloading imageio-2.38.1-py3-none-any.whl (328 kB)
Downloading multidict-7.2.1-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (516 kB)
Downloading opentelemetry_api-1.45.2-py3-none-any.whl (60 kB)
Downloading proglog-0.1.12-py3-none-any.whl (6.3 kB)
Downloading proto_plus-1.29.0-py3-none-any.whl (50 kB)
Downloading protobuf-7.36.2-cp310-abi3-manylinux2014_x86_64.whl (343 kB)
Downloading pyee-14.0.0-py3-none-any.whl (15 kB)
Downloading pyOpenSSL-24.2.1-py3-none-any.whl (58 kB)
Downloading pyparsing-3.3.3-py3-none-any.whl (126 kB)
Downloading tabulate-0.10.0-py3-none-any.whl (39 kB)
Downloading trio-0.35.0-py3-none-any.whl (513 kB)
Downloading trio_websocket-0.12.2-py3-none-any.whl (21 kB)
Downloading typing_extensions-4.16.0-py3-none-any.whl (45 kB)
Downloading uritemplate-4.2.0-py3-none-any.whl (11 kB)
Downloading urllib3-2.8.0-py3-none-any.whl (135 kB)
Downloading PySocks-1.7.1-py3-none-any.whl (16 kB)
Downloading websocket_client-1.9.2-py3-none-any.whl (95 kB)
Downloading yarl-1.25.1-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (117 kB)
Downloading aiohappyeyeballs-2.7.1-py3-none-any.whl (15 kB)
Downloading aiosignal-1.4.0-py3-none-any.whl (7.5 kB)
Downloading attrs-26.1.0-py3-none-any.whl (67 kB)
Downloading certifi-2026.10.23-py3-none-any.whl (135 kB)
Downloading cffi-2.1.1-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl (221 kB)
Downloading frozenlist-1.8.0-cp313-cp313-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl (234 kB)
Downloading imageio_ffmpeg-0.8.0-py3-none-manylinux_2_28_x86_64.whl (68.0 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 68.0/68.0 MB 80.5 MB/s  0:00:00
Downloading numpy-2.5.4-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl (16.7 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 16.7/16.7 MB 155.3 MB/s  0:00:00
Downloading oauth2client-4.1.3-py2.py3-none-any.whl (98 kB)
Downloading outcome-1.3.0.post0-py2.py3-none-any.whl (10 kB)
Downloading propcache-0.5.4-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (234 kB)
Downloading pyasn1-0.6.5-py3-none-any.whl (84 kB)
Downloading pyasn1_modules-0.4.2-py3-none-any.whl (181 kB)
Downloading pyyaml-6.0.3-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (801 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 801.6/801.6 kB 131.5 MB/s  0:00:00
Downloading requests_oauthlib-2.0.0-py2.py3-none-any.whl (24 kB)
Downloading oauthlib-4.0.1-py3-none-any.whl (161 kB)
Downloading rsa-4.9.1-py3-none-any.whl (34 kB)
Downloading six-1.17.0-py2.py3-none-any.whl (11 kB)
Downloading sniffio-1.3.1-py3-none-any.whl (10 kB)
Downloading soupsieve-3.0.4-py3-none-any.whl (42 kB)
Downloading wsproto-1.3.2-py3-none-any.whl (24 kB)
Downloading h11-0.16.0-py3-none-any.whl (37 kB)
Downloading future-1.0.0-py3-none-any.whl (491 kB)
Downloading pycparser-3.12-py3-none-any.whl (62 kB)
Downloading sortedcontainers-2.4.0-py2.py3-none-any.whl (29 kB)
Downloading tqdm-4.70.1-py3-none-any.whl (80 kB)
Installing collected packages: sortedcontainers, yt-dlp, websocket-client, urllib3, uritemplate, typing-extensions, tqdm, tabulate, soupsieve, sniffio, six, PyYAML, python-dotenv, pysocks, pyparsing, pycparser, pyasn1, protobuf, propcache, Pillow, oauthlib, numpy, multidict, imageio_ffmpeg, idna, h11, greenlet, future, frozenlist, decorator, charset_normalizer, certifi, attrs, aiohappyeyeballs, yarl, wsproto, rsa, requests, pyee, pyasn1-modules, proto-plus, proglog, outcome, opentelemetry-api, opencv-python, imageio, httplib2, googleapis-common-protos, ffmpeg-python, cffi, beautifulsoup4, aiosignal, trio, requests-oauthlib, playwright, oauth2client, moviepy, cryptography, aiohttp, trio-websocket, pyOpenSSL, google-auth, edge-tts, selenium, google-auth-oauthlib, google-auth-httplib2, google-api-core, google-api-python-client, pydrive2

Successfully installed Pillow-11.3.0 PyYAML-6.0.3 aiohappyeyeballs-2.7.1 aiohttp-3.14.5 aiosignal-1.4.0 attrs-26.1.0 beautifulsoup4-4.15.0 certifi-2026.10.23 cffi-2.1.1 charset_normalizer-3.5.2 cryptography-43.0.3 decorator-5.3.1 edge-tts-7.3.1 ffmpeg-python-0.2.0 frozenlist-1.8.0 future-1.0.0 google-api-core-2.43.2 google-api-python-client-2.201.0 google-auth-2.62.1 google-auth-httplib2-0.4.4 google-auth-oauthlib-1.5.0 googleapis-common-protos-1.76.0 greenlet-3.5.6 h11-0.16.0 httplib2-0.32.1 idna-3.20 imageio-2.38.1 imageio_ffmpeg-0.8.0 moviepy-2.2.1 multidict-7.2.1 numpy-2.5.4 oauth2client-4.1.3 oauthlib-4.0.1 opencv-python-4.14.0.94 opentelemetry-api-1.45.2 outcome-1.3.0.post0 playwright-1.64.1 proglog-0.1.12 propcache-0.5.4 proto-plus-1.29.0 protobuf-7.36.2 pyOpenSSL-24.2.1 pyasn1-0.6.5 pyasn1-modules-0.4.2 pycparser-3.12 pydrive2-1.21.3 pyee-14.0.0 pyparsing-3.3.3 pysocks-1.7.1 python-dotenv-1.2.4 requests-2.34.2 requests-oauthlib-2.0.0 rsa-4.9.1 selenium-4.52.0 six-1.17.0 sniffio-1.3.1 sortedcontainers-2.4.0 soupsieve-3.0.4 tabulate-0.10.0 tqdm-4.70.1 trio-0.35.0 trio-websocket-0.12.2 typing-extensions-4.16.0 uritemplate-4.2.0 urllib3-2.8.0 websocket-client-1.9.2 wsproto-1.3.2 yarl-1.25.1 yt-dlp-2026.10.26

[notice] A new release of pip is available: 26.2.1 -> 26.3
[notice] To update, run: /home/user/youtube_shorts_automation/.venv/bin/python -m pip install --upgrade pip

PIP_EXIT_CODE=0
```

## FFmpeg sürümü — tam çıktı

```text
$ ffmpeg -version
ffmpeg version 7.1.5-0+deb13u1 Copyright (c) 2000-2026 the FFmpeg developers
built with gcc 14 (Debian 14.2.0-19)
configuration: --prefix=/usr --extra-version=0+deb13u1 --toolchain=hardened --libdir=/usr/lib/x86_64-linux-gnu --incdir=/usr/include/x86_64-linux-gnu --arch=amd64 --enable-gpl --disable-stripping --disable-libmfx --disable-omx --enable-gnutls --enable-libaom --enable-libass --enable-libbs2b --enable-libcdio --enable-libcodec2 --enable-libdav1d --enable-libflite --enable-libfontconfig --enable-libfreetype --enable-libfribidi --enable-libglslang --enable-libgme --enable-libgsm --enable-libharfbuzz --enable-libmp3lame --enable-libmysofa --enable-libopenjpeg --enable-libopenmpt --enable-libopus --enable-librubberband --enable-libshine --enable-libsnappy --enable-libsoxr --enable-libspeex --enable-libtheora --enable-libtwolame --enable-libvidstab --enable-libvorbis --enable-libvpx --enable-libwebp --enable-libx265 --enable-libxml2 --enable-libxvid --enable-libzimg --enable-openal --enable-opencl --enable-opengl --disable-sndio --enable-libvpl --enable-libdc1394 --enable-libdrm --enable-libiec61883 --enable-chromaprint --enable-frei0r --enable-ladspa --enable-libbluray --enable-libcaca --enable-libdvdnav --enable-libdvdread --enable-libjack --enable-libpulse --enable-librabbitmq --enable-librist --enable-libsrt --enable-libssh --enable-libsvtav1 --enable-libx264 --enable-libzmq --enable-libzvbi --enable-lv2 --enable-sdl2 --enable-libplacebo --enable-librav1e --enable-pocketsphinx --enable-librsvg --enable-libjxl --enable-shared
libavutil      59. 39.100 / 59. 39.100
libavcodec     61. 19.101 / 61. 19.101
libavformat    61.  7.103 / 61.  7.103
libavdevice    61.  3.100 / 61.  3.100
libavfilter    10.  5.100 / 10.  5.100
libswscale      8.  3.100 /  8.  3.100
libswresample   5.  3.100 /  5.  3.100
libpostproc    58.  3.100 / 58.  3.100

FFMPEG_EXIT_CODE=0
```

## Proje ağacı — tam çıktı

```text
youtube_shorts_automation
|-- .env.example
|-- .gitignore
|-- README.md
|-- config
|   |-- __init__.py
|   |-- constants.py
|   `-- settings.py
|-- docs
|   |-- ARCHITECTURE.md
|   `-- setup
|       |-- DEPENDENCY_DECISIONS.md
|       |-- INSTALLATION_REPORT.md
|       `-- requirements.requested.txt
|-- logs
|   `-- README.md
|-- main.py
|-- output
|   |-- .gitkeep
|   `-- README.md
|-- requirements.lock.txt
|-- requirements.txt
|-- setup_reports
|   |-- 01-pip-requested.log
|   |-- 02-apt-tools.log
|   |-- 03-pypi-metadata.json
|   |-- 04-pip-compatible.log
|   |-- 05-playwright-install.log
|   |-- 06-ffmpeg-version.txt
|   |-- 07-validation.log
|   |-- 08-tree.txt
|   |-- 09-environment-check.log
|   |-- 10-playwright-system-deps.log
|   |-- 11-validation-final.log
|   `-- environment.json
|-- src
|   |-- __init__.py
|   |-- content_generation
|   |   `-- __init__.py
|   |-- media_processing
|   |   `-- __init__.py
|   |-- utils
|   |   `-- __init__.py
|   `-- youtube_upload
|       `-- __init__.py
`-- tests
    |-- __init__.py
    |-- test_environment.py
    `-- test_scaffold.py

13 directories, 36 files
```

## Son doğrulama — tam çıktı

```text
--- pip check ---
No broken requirements found.
--- Python syntax ---
--- Offline tests ---
test_all_required_python_modules_import (test_environment.EnvironmentTests.test_all_required_python_modules_import) ... ok
test_chromium_runs_local_page_without_external_requests (test_environment.EnvironmentTests.test_chromium_runs_local_page_without_external_requests) ... ok
test_ffmpeg_encodes_vertical_h264_aac (test_environment.EnvironmentTests.test_ffmpeg_encodes_vertical_h264_aac) ... ok
test_project_root_is_absolute (test_scaffold.ScaffoldTests.test_project_root_is_absolute) ... ok
test_required_directories_exist (test_scaffold.ScaffoldTests.test_required_directories_exist) ... ok
test_secrets_are_not_required_for_configuration (test_scaffold.ScaffoldTests.test_secrets_are_not_required_for_configuration) ... ok
test_vertical_video_defaults (test_scaffold.ScaffoldTests.test_vertical_video_defaults) ... ok

----------------------------------------------------------------------
Ran 7 tests in 2.073s

OK
--- Environment check ---
{
  "python": "3.13.16",
  "platform": "Linux-6.1.158+-x86_64-with-glibc2.41",
  "packages": {
    "google-api-python-client": {
      "ok": true,
      "version": "2.201.0"
    },
    "google-auth-oauthlib": {
      "ok": true,
      "version": "1.5.0"
    },
    "google-auth-httplib2": {
      "ok": true,
      "version": "0.4.4"
    },
    "edge-tts": {
      "ok": true,
      "version": "7.3.1"
    },
    "moviepy": {
      "ok": true,
      "version": "2.2.1"
    },
    "ffmpeg-python": {
      "ok": true,
      "version": "0.2.0"
    },
    "opencv-python": {
      "ok": true,
      "version": "4.14.0.94"
    },
    "Pillow": {
      "ok": true,
      "version": "11.3.0"
    },
    "playwright": {
      "ok": true,
      "version": "1.64.1"
    },
    "selenium": {
      "ok": true,
      "version": "4.52.0"
    },
    "pydrive2": {
      "ok": true,
      "version": "1.21.3"
    },
    "python-dotenv": {
      "ok": true,
      "version": "1.2.4"
    },
    "aiohttp": {
      "ok": true,
      "version": "3.14.5"
    },
    "requests": {
      "ok": true,
      "version": "2.34.2"
    },
    "beautifulsoup4": {
      "ok": true,
      "version": "4.15.0"
    },
    "yt-dlp": {
      "ok": true,
      "version": "2026.10.26"
    }
  },
  "tools": {
    "ffmpeg": {
      "ok": true,
      "path": "/usr/bin/ffmpeg",
      "version": "ffmpeg version 7.1.5-0+deb13u1 Copyright (c) 2000-2026 the FFmpeg developers"
    },
    "ffprobe": {
      "ok": true,
      "path": "/usr/bin/ffprobe",
      "version": "ffprobe version 7.1.5-0+deb13u1 Copyright (c) 2007-2026 the FFmpeg developers"
    },
    "tree": {
      "ok": true,
      "path": "/usr/bin/tree",
      "version": "tree v2.2.1 © 1996 - 2024 by Steve Baker, Thomas Moore, Francesc Rocher, Florian Sesser, Kyosuke Tokoro"
    }
  },
  "ok": true
}

FINAL_VALIDATION_EXIT_CODE=0
```
