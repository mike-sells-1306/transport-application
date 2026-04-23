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
      - button "Search for routes" [ref=e26] [cursor=pointer]: Search routes
    - navigation "Main navigation" [ref=e27]:
      - link "Account" [ref=e28] [cursor=pointer]:
        - /url: "#account"
      - link "FAQ" [ref=e29] [cursor=pointer]:
        - /url: "#faq"
      - link "Customer Support" [ref=e30] [cursor=pointer]:
        - /url: "#support"
      - button "Accessibility" [ref=e31] [cursor=pointer]
  - button "Toggle sidebar" [expanded] [ref=e32] [cursor=pointer]:
    - generic [ref=e33]: ‹
  - main "Transport for North West" [ref=e34]:
    - application "Interactive map of North West England" [ref=e35]
    - generic [ref=e36]:
      - generic [ref=e37]: Map style
      - combobox "Map style" [ref=e38] [cursor=pointer]
      - button "View weather updates" [active] [ref=e39] [cursor=pointer]
      - button "View service notifications" [ref=e41] [cursor=pointer]
```