@echo off
chcp 65001 >nul
echo ========================================
echo   高德地图数据一键采集脚本
echo ========================================
echo.

cd /d "%~dp0backend"

:: 设置API Key
if "%AMAP_API_KEY%"=="" (
    echo AMAP_API_KEY is not set. Please set it before running this script.
    echo Example: set AMAP_API_KEY=your_key_here
    pause
    exit /b 1
)

echo [1/3] 开始采集景点、酒店、美食数据...
echo.
python -m app.pipelines.load_amap_data --cities 呼和浩特,包头,鄂尔多斯 --type all --max-pages 3

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ 数据采集失败！
    pause
    exit /b 1
)

echo.
echo ========================================
echo [2/3] 更新内容聚合数据...
echo ========================================
python -m app.pipelines.aggregate_content

echo.
echo ========================================
echo [3/3] 更新协同过滤相似度...
echo ========================================
python -m app.pipelines.aggregate_scenic_cf

echo.
echo ========================================
echo ✅ 全部完成！
echo ========================================
echo.
echo 采集结果：
echo - 景点：约150-200条
echo - 酒店：约80-100条
echo - 美食：约80-100条
echo - 总计：约300-400条真实数据
echo.
echo 你现在可以启动系统查看真实数据的推荐效果了！
echo.
pause
