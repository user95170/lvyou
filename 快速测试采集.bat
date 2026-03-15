@echo off
chcp 65001 >nul
echo ========================================
echo   快速测试采集（仅采集呼和浩特景点）
echo ========================================
echo.

cd /d "%~dp0backend"

:: 设置API Key
set AMAP_API_KEY=0e55c251c510be470acd9bace0efe62f

echo 开始测试采集...
echo.
python -m app.pipelines.load_amap_data --cities 呼和浩特 --type scenic --max-pages 2 --dry-run

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ 测试失败！请检查：
    echo 1. Python环境是否正确
    echo 2. 网络连接是否正常
    echo 3. 依赖包是否安装完整
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✅ 测试成功！
echo ========================================
echo.
echo 现在可以运行【一键采集数据.bat】进行正式采集
echo.
pause
