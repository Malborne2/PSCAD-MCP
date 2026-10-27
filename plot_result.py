import sys, json
sys.path.insert(0, ".")
from pscad_mcp import server as s

path = r"C:\GitHub\PSCAD-MCP\demo_project\mcp_demo.gf81_x86\mcp_demo.psout"
s.pscad_connect()
trace = s.pscad_get_trace_data(path, "Root/Main/Iload/0/1", max_points=801)
print("num_samples:", trace["num_samples"], "min:", trace["min"], "max:", trace["max"], "mean:", trace["mean"])

points = trace["points"]
t = [p[0] for p in points]
v = [p[1] for p in points]

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(9, 4.5), dpi=130)
ax.plot(t, v, color="#2563eb", linewidth=1.3)
ax.set_title("mcp_demo: Load Current (Iload) -- real PSCAD/EMTDC run via MCP tools")
ax.set_xlabel("Time (s)")
ax.set_ylabel("Current (kA)")
ax.grid(True, alpha=0.3)
ax.axhline(0, color="black", linewidth=0.6)
fig.tight_layout()
out_png = "demo_project/mcp_demo_result.png"
fig.savefig(out_png)
print("saved:", out_png)
