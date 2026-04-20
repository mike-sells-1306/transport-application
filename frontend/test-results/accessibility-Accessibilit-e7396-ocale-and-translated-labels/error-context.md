# Page snapshot

```yaml
- generic [ref=e1]:
  - navigation "Primary sidebar" [ref=e4]:
    - heading "Transport for North West" [level=1] [ref=e6]
    - generic [ref=e7]:
      - generic [ref=e8]: Where would you like to travel today?
      - generic [ref=e9]:
        - generic [ref=e12]:
          - generic [ref=e13]: Select departure station
          - textbox "Select departure station" [ref=e14]:
            - /placeholder: Search…
          - paragraph [ref=e15]
        - generic [ref=e20]:
          - generic [ref=e21]: Select arrival station
          - textbox "Select arrival station" [ref=e22]:
            - /placeholder: to
          - paragraph [ref=e23]
        - button "Swap departure and arrival stations" [ref=e24] [cursor=pointer]
    - navigation "Main navigation" [ref=e26]:
      - link "Account" [ref=e27] [cursor=pointer]:
        - /url: "#account"
      - link "FAQ" [ref=e28] [cursor=pointer]:
        - /url: "#faq"
      - link "Customer Support" [ref=e29] [cursor=pointer]:
        - /url: "#support"
      - button "Accessibility" [active] [ref=e30] [cursor=pointer]
  - button "Toggle sidebar" [expanded] [ref=e31] [cursor=pointer]:
    - generic [ref=e32]: ‹
  - main "Transport for North West" [ref=e33]:
    - application "Interactive map of North West England" [ref=e34]
    - generic [ref=e35]:
      - generic [ref=e36]: Map Style
      - combobox "Map style selector" [ref=e37] [cursor=pointer]
      - button "View weather updates" [ref=e38] [cursor=pointer]
      - button "View service notifications" [ref=e40] [cursor=pointer]
```