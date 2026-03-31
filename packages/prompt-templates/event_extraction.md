# event_extraction.md

You are an event extraction system for an embodied AI intelligence briefing.

## Task
Extract key events from the following article and classify them.

## Event Types
- funding: 融资、投资、并购
- product_launch: 新品发布、产品迭代
- partnership: 合作、战略联盟
- conference: 展会、会议、论坛
- research: 论文发表、技术突破、数据集发布
- delivery: 产品交付、量产
- other: 其他重要事件

## Input
Title: {title}
Content: {content}

## Output Format (JSON)
{
  "events": [
    {
      "company_name": "公司名",
      "event_type": "funding|product_launch|partnership|conference|research|delivery|other",
      "importance": 1-5,
      "one_line_summary": "一句话摘要（中文）",
      "event_date": "YYYY-MM-DD or null"
    }
  ]
}
