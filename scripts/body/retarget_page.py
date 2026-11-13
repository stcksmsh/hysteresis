"""WO32C: patch a one-arm ensemble_preview page (a copy) for the pillar mount v2p. Rules: docs/RETARGET_RULES.md (j). Usage: retarget_page.py IN.html OUT.html

The template crates/hyst-previz/src/ensemble.html is not edited. Every replacement must match exactly once, else the script stops.
Floor and stage move to z = F (0.053 - 1.0), the pedestal becomes a 0.14 m square column from F to 0.053 with the three base-yaw spokes on its top, the projector's patch
and the arm's shadow land on the new floor, the plumb line from the hand is dropped. The camera is unchanged.
"""
import sys

import make_arm_v2p as P

F = P.FLOOR
H = P.COL_HALF
TOP = P.TOP

PILLAR = ("const PH=%r,PT=%r,PF=%r;\n"
          "      const cc=[[-PH,-PH],[PH,-PH],[PH,PH],[-PH,PH]];\n"
          "      for(let i=0;i<4;i++){const a=cc[i],b=cc[(i+1)%%4],n=[(a[0]+b[0])/2,(a[1]+b[1])/2];\n"
          "        const q=[[arm[0][0]+a[0],arm[0][1]+a[1],PF],[arm[0][0]+b[0],arm[0][1]+b[1],PF],[arm[0][0]+b[0],arm[0][1]+b[1],PT],[arm[0][0]+a[0],arm[0][1]+a[1],PT]];\n"
          "        const lit=.55+.45*Math.max(0,dot(norm([n[0],n[1],0]),LIGHT));\n"
          "        if(dot([n[0],n[1],0],sub(eye,arm[0]))>0) fill(q.map(project),rgb([40,52,64],lit));}\n"
          "      fill(cc.map(c=>project([arm[0][0]+c[0],arm[0][1]+c[1],PT])),'#27343f');\n"
          "      for(let spoke=0;spoke<3;spoke++) {\n"
          "        const angle=state.turns[id][0]*Math.PI/180+spoke*2*Math.PI/3, mark=r=>[arm[0][0]+r*Math.cos(angle),arm[0][1]+r*Math.sin(angle),PT+.0015];\n"
          "        line(mark(.025),mark(.062),spoke?rgb(HOUSING,2.6):colors[id%%4],spoke?2:4);\n"
          "      }\n"
          "      drum(arm[0],.05,arm[1][2],rgb(HOUSING,1),rgb(HOUSING,2),PT);\n") % (H, TOP, F)


def rep(s, old, new):
    assert s.count(old) == 1, (s.count(old), old[:70])
    return s.replace(old, new)


def patch(s):
    s = rep(s, "[[-1.65,-1.65,0],[1.65,-1.65,0],[1.65,1.65,0],[-1.65,1.65,0]]", f"[[-1.65,-1.65,{F}],[1.65,-1.65,{F}],[1.65,1.65,{F}],[-1.65,1.65,{F}]]")
    s = rep(s, "const centre=project([0,0,0]),", f"const centre=project([0,0,{F}]),")
    s = rep(s, "line([r*Math.cos(a),r*Math.sin(a),.004],[r*Math.cos(b),r*Math.sin(b),.004],", f"line([r*Math.cos(a),r*Math.sin(a),{F}+.004],[r*Math.cos(b),r*Math.sin(b),{F}+.004],")
    s = rep(s, "const toFloor=-from[2]/out[2];", f"const toFloor=({F}-from[2])/out[2];")
    s = rep(s, "const cast=p=>{const s=PROJECTOR[2]/(PROJECTOR[2]-p[2]);return [p[0]*s,p[1]*s,.003];};",
            f"const cast=p=>{{const s=(PROJECTOR[2]-({F}))/(PROJECTOR[2]-p[2]);return [p[0]*s,p[1]*s,{F}+.003];}};")
    s = rep(s, "under=project([hand[0],hand[1],0])", f"under=project([hand[0],hand[1],{F}])")
    s = rep(s, "line(hand,[hand[0],hand[1],.003],'#4d626d',1);", "")
    a = s.index("drum(arm[0],.15,.012,'#141d25','#1d2a34');")
    b = s.index("drum(arm[0],.05,arm[1][2],rgb(HOUSING,1),rgb(HOUSING,2),.035);") + len("drum(arm[0],.05,arm[1][2],rgb(HOUSING,1),rgb(HOUSING,2),.035);")
    return s[:a] + PILLAR + s[b:]


if __name__ == "__main__":
    src, dst = sys.argv[1:3]
    open(dst, "w").write(patch(open(src).read()))
