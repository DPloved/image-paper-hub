# Image Paper Hub｜图像相关论文收集

一个可直接部署到 GitHub Pages 的静态论文收录网站，风格参考论文清单 README：

- 顶部简介与更新时间
- 总论文数、分类数、arXiv、代码统计
- 分类统计表
- 分类、年份、关键词筛选
- 结构化数据文件 `papers.json`

## 本地预览

用任意静态服务器打开即可，例如：

```bash
python -m http.server 8000
```

然后访问 `http://localhost:8000`。

## 添加论文

编辑 `papers.json` 的 `papers` 数组，新增一条记录：

```json
{
  "id": "paper-id",
  "title": "Paper Title",
  "authors": "Author et al.",
  "venue": "CVPR 2026",
  "year": 2026,
  "category": "sr",
  "tags": ["Super-Resolution", "Attention"],
  "summary": "一句话总结论文贡献。",
  "links": {
    "paper": "",
    "arxiv": "",
    "code": ""
  },
  "status": "待补充代码"
}
```

分类配置在 `papers.json` 的 `categories` 数组中。

## GitHub Pages

上传到 GitHub 后，在仓库设置中开启 Pages：

- Source: `Deploy from a branch`
- Branch: `main`
- Folder: `/root`

保存后 GitHub 会生成网站链接。
