这个文件夹里的图会并入首页背景轮播。

项目自带 miku_00.jpg ~ miku_07.jpg 共 8 张原创插画
（程序绘制 / 后期处理，非官方立绘），以 MIT 许可证随项目发布，
可以直接使用或替换。

想换成官方立绘（仅个人非商用）：
  1. 去 piapro（https://piapro.net）下载初音未来官方/授权立绘，
     并遵守其角色使用规约与署名要求。
  2. 把下载的图放到任意文件夹，例如 D:\miku_pics
  3. 运行：
       .venv\Scripts\python.exe work\import_miku.py D:\miku_pics
     脚本会自动转 JPEG、缩放到背景尺寸，存成 miku_10.jpg、miku_11.jpg…

也可以直接把 jpg/png 丢进本文件夹（建议 1600x1000 左右，横版）。

说明：
  - 程序不会联网抓取版权图片。
  - 官方立绘请勿用于任何商业用途，也不要提交进本仓库。
