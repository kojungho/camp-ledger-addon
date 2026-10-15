# 플랫폼 화면 시작 검사

테스트용 Android 가상 기기에 캠핑 노트 APK를 먼저 설치합니다. 실제 예약 계정이나 HA 연결키 없이 세 플랫폼 화면을 각각 두 번 열어 WebView 초기화와 닫기를 검사합니다. 테스트 전용 APK는 배포 APK와 같은 키로 서명해야 합니다.

`ANDROID_SDK_ROOT`, `JAVA_HOME`, `CAMP_ANDROID_TEST_DIR`(저장소 밖 임시 경로), `CAMP_ANDROID_TEST_SERIAL`(테스트 가상 기기), `CAMP_APK_KEYSTORE`, `CAMP_APK_STOREPASS`를 설정하고 `bash android/camp-note/tests/run-startup-test.sh`를 실행합니다. 암호는 로그나 소스에 기록하지 않습니다. 스크립트는 선택한 가상 기기에 테스트 APK를 설치하며 기존 앱 데이터를 지우지 않습니다.

결과에 `result=PASS`가 있어야 성공입니다. 기존 1.0.13은 `PlatformActivity.onCreate → PhoneWindow.getInsetsController`의 NullPointerException으로 종료되었고, 1.0.14에서 같은 검사 6회가 통과했습니다. 플랫폼 실제 계정 로그인·예약 수집 검사와는 별도입니다.
