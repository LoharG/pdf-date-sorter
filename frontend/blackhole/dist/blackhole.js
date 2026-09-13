"use strict";(()=>{var We=`
attribute vec2 aPos;
varying vec2 vUv;
void main() {
  vUv = aPos * 0.5 + 0.5;
  gl_Position = vec4(aPos, 0.0, 1.0);
}
`,Xe=`
precision highp float;

#define MAX_STEPS 460
#define WIND_CYCLE 46.0

varying vec2 vUv;

uniform vec2  uRes;
uniform float uTime;
uniform vec3  uCamPos;
uniform vec3  uRight;
uniform vec3  uUp;
uniform vec3  uFwd;
uniform float uTanHalf;
uniform vec2  uFocus;
uniform float uSteps;
uniform float uSkyR;
uniform float uDiskIn;
uniform float uDiskOut;
uniform float uThick;
uniform float uDensity;
uniform float uSpin;
uniform float uGrain;
uniform float uBright;
uniform float uDoppler;
uniform vec3  uHot;
uniform vec3  uMid;
uniform vec3  uCool;
uniform float uStars;
uniform float uEncode;
uniform vec2  uJitter;
uniform float uSeed;

float hash13(vec3 p) {
  p = fract(p * 0.3183099 + vec3(0.1, 0.2, 0.3));
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float vnoise(vec3 x) {
  vec3 i = floor(x);
  vec3 f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  float n000 = hash13(i + vec3(0.0, 0.0, 0.0));
  float n100 = hash13(i + vec3(1.0, 0.0, 0.0));
  float n010 = hash13(i + vec3(0.0, 1.0, 0.0));
  float n110 = hash13(i + vec3(1.0, 1.0, 0.0));
  float n001 = hash13(i + vec3(0.0, 0.0, 1.0));
  float n101 = hash13(i + vec3(1.0, 0.0, 1.0));
  float n011 = hash13(i + vec3(0.0, 1.0, 1.0));
  float n111 = hash13(i + vec3(1.0, 1.0, 1.0));
  return mix(
    mix(mix(n000, n100, f.x), mix(n010, n110, f.x), f.y),
    mix(mix(n001, n101, f.x), mix(n011, n111, f.x), f.y),
    f.z
  );
}

float fbm(vec3 p, float lod) {
  float a = 0.5;
  float s = 0.0;
  for (int i = 0; i < 4; i++) {
    s += (i == 3 ? a * lod : a) * vnoise(p);
    p = p * 2.03 + vec3(11.3, 7.1, 3.7);
    a *= 0.5;
  }
  return s;
}

void gasAt(vec3 p, float rd, float dt, out float dens, out vec3 tint, out float heat) {
  float rn = clamp((rd - uDiskIn) / max(0.001, uDiskOut - uDiskIn), 0.0, 1.0);

  float tk = uThick * (0.35 + 1.25 * rn);
  float v = p.y / tk;
  float sheet = exp(-v * v);

  float lod = clamp(1.0 - dt * uGrain * 14.0, 0.0, 1.0);

  float phi = atan(p.z, p.x);
  float omega = uSpin * pow(uDiskIn / rd, 1.5);
  float lr = log(rd) * 1.1 + uSpin * uTime * 0.05;

  float u = uTime / WIND_CYCLE;
  float fA = fract(u);
  float fB = fract(u + 0.5);
  float w = abs(2.0 * fA - 1.0);

  float cloudsA = fbm(vec3(vec2(cos(phi + omega * fA * WIND_CYCLE),
                                sin(phi + omega * fA * WIND_CYCLE)) * (rd * uGrain), lr), lod);
  float cloudsB = fbm(vec3(vec2(cos(phi + omega * fB * WIND_CYCLE),
                                sin(phi + omega * fB * WIND_CYCLE)) * (rd * uGrain), lr + 40.0), lod);
  float clouds = mix(cloudsA, cloudsB, w);

  float filaments = clouds * clouds * 1.75;

  float inner = smoothstep(0.0, 0.07, rn);
  float outer = 1.0 - smoothstep(0.45, 1.0, rn);
  float prof = inner * outer * pow(uDiskIn / rd, 2.0);

  dens = max(0.0, filaments * 1.5 - 0.30) * sheet * prof * uDensity * 4.6;

  heat = pow(uDiskIn / rd, 0.8) * (0.72 + 0.55 * clouds);
  tint = mix(uCool, uMid, smoothstep(0.10, 0.52, heat));
  tint = mix(tint, uHot, smoothstep(0.52, 1.05, heat));
}

vec3 starField(vec3 d) {
  vec3 a = abs(d);
  vec2 uv;
  float face;
  if (a.x >= a.y && a.x >= a.z)      { uv = d.yz / a.x; face = d.x > 0.0 ? 0.0 : 1.0; }
  else if (a.y >= a.z)               { uv = d.xz / a.y; face = d.y > 0.0 ? 2.0 : 3.0; }
  else                               { uv = d.xy / a.z; face = d.z > 0.0 ? 4.0 : 5.0; }

  vec3 col = vec3(0.0);
  for (int k = 0; k < 3; k++) {
    float sc = 90.0 * pow(2.2, float(k));
    vec2 p = uv * sc;
    vec2 id = floor(p);
    vec2 f = fract(p) - 0.5;
    float h = hash13(vec3(id, face * 19.0));
    if (h > 0.965) {
      vec2 off = vec2(hash13(vec3(id, face + 11.0)), hash13(vec3(id, face + 23.0)));
      float dd = length(f - (off - 0.5) * 0.7);
      float s = smoothstep(0.055, 0.0, dd);
      float warm = hash13(vec3(id, face + 51.0));
      col += s * (0.6 + 4.5 * fract(h * 97.0))
           * mix(vec3(0.72, 0.82, 1.0), vec3(1.0, 0.88, 0.72), warm)
           / pow(2.2, float(k));
    }
  }
  col += vec3(0.013, 0.017, 0.030) * fbm(d * 2.6, 1.0);
  return col;
}

void main() {
  vec2 uv = (gl_FragCoord.xy + uJitter - uFocus * uRes) / uRes.y;
  vec3 dir = normalize(uFwd + (uv.x * uRight + uv.y * uUp) * 2.0 * uTanHalf);

  vec3 pos = uCamPos;
  vec3 vel = dir;

  vec3 hv = cross(pos, vel);
  float h2 = dot(hv, hv);
  float h = sqrt(h2);
  float swept = 0.0;

  vec3 col = vec3(0.0);
  float transmit = 1.0;
  bool captured = false;

  float jitter = fract(sin(dot(gl_FragCoord.xy + uSeed, vec2(12.9898, 78.233))) * 43758.5453);

  for (int i = 0; i < MAX_STEPS; i++) {
    if (float(i) >= uSteps) break;

    float r2 = dot(pos, pos);
    float r = sqrt(r2);

    if (r < 1.0) { captured = true; break; }
    if (r > uSkyR && dot(pos, vel) > 0.0) break;
    if (transmit < 0.004) break;

    float dt = clamp(0.14 * (r - 1.0), 0.025, 1.1);

    if (r < uDiskOut * 1.25) {
      float rn = clamp((r - uDiskIn) / max(0.001, uDiskOut - uDiskIn), 0.0, 1.0);
      float tk = uThick * (0.35 + 1.25 * rn);
      dt = min(dt, max(tk * 0.38, abs(pos.y) * 0.5));
    }

    swept += h * dt / r2;

    float deep = exp(-1.3 * max(0.0, swept - 4.6));

    jitter = fract(jitter + 0.6180339887);
    vec3 mid = pos + vel * (dt * jitter);
    float rd = length(mid.xz);

    if (rd > uDiskIn && rd < uDiskOut && abs(mid.y) < uThick * 5.0) {
      float dens;
      float heat;
      vec3 tint;
      gasAt(mid, rd, dt, dens, tint, heat);

      if (dens > 0.001) {
        vec3 tang = normalize(cross(vec3(0.0, 1.0, 0.0), vec3(mid.x, 0.0, mid.z)));
        float beta = min(0.85, sqrt(0.5 / max(rd, 1.5)));
        float gam = inversesqrt(max(1e-4, 1.0 - beta * beta));
        vec3 toObs = -normalize(vel);
        float g = 1.0 / (gam * (1.0 - beta * dot(tang, toObs)));
        g *= sqrt(max(0.05, 1.0 - 1.0 / rd));
        float boost = pow(max(g, 0.02), 3.0 * uDoppler);

        vec3 shift = mix(
          vec3(1.0),
          g > 1.0 ? vec3(0.86, 0.94, 1.14) : vec3(1.15, 0.82, 0.62),
          clamp(abs(g - 1.0) * 1.6, 0.0, 1.0) * uDoppler
        );

        float emit = uBright * (0.26 + 2.0 * heat * heat);
        col += tint * shift * (emit * boost * dens * transmit * dt * deep);
        transmit *= exp(-dens * 0.30 * dt);
      }
    }

    vec3 acc = -1.5 * h2 * pos / (r2 * r2 * r);
    vel += acc * dt;
    pos += vel * dt;
  }

  if (!captured && uStars > 0.001) {
    vec3 toHole = normalize(-uCamPos);
    float sI = length(cross(normalize(dir), toHole));
    float sS = length(cross(normalize(vel), toHole));
    float stretch = clamp(sI / max(1e-3, sS), 1.0, 40.0);
    col += starField(normalize(vel)) * uStars * transmit / stretch;
  }

  if (uEncode > 0.5) col = col / (1.0 + col);
  gl_FragColor = vec4(col, 1.0);
}
`,Ye=`
precision highp float;
varying vec2 vUv;
uniform sampler2D uCur;
uniform sampler2D uPrev;
uniform float uAlpha;

void main() {
  vec3 c = texture2D(uCur, vUv).rgb;
  vec3 p = texture2D(uPrev, vUv).rgb;
  gl_FragColor = vec4(mix(p, c, uAlpha), 1.0);
}
`,Ve=`
precision highp float;
varying vec2 vUv;
uniform sampler2D uTex;
uniform vec2 uTexel;
uniform float uDecode;
uniform float uPack;
uniform float uThreshold;

void main() {
  vec3 s = texture2D(uTex, vUv + uTexel * vec2(-1.0, -1.0)).rgb
         + texture2D(uTex, vUv + uTexel * vec2( 1.0, -1.0)).rgb
         + texture2D(uTex, vUv + uTexel * vec2(-1.0,  1.0)).rgb
         + texture2D(uTex, vUv + uTexel * vec2( 1.0,  1.0)).rgb;
  s *= 0.25;
  if (uDecode > 0.5) s = s / max(vec3(0.002), 1.0 - s);
  float l = max(s.r, max(s.g, s.b));
  s *= max(0.0, l - uThreshold) / max(0.0001, l);
  gl_FragColor = vec4(s * uPack, 1.0);
}
`,qe=`
precision highp float;
varying vec2 vUv;
uniform sampler2D uTex;
uniform vec2 uStep;

void main() {
  vec3 s = texture2D(uTex, vUv).rgb * 0.2270270;
  s += (texture2D(uTex, vUv + uStep * 1.3846154).rgb
      + texture2D(uTex, vUv - uStep * 1.3846154).rgb) * 0.3162162;
  s += (texture2D(uTex, vUv + uStep * 3.2307692).rgb
      + texture2D(uTex, vUv - uStep * 3.2307692).rgb) * 0.0702702;
  gl_FragColor = vec4(s, 1.0);
}
`,Ke=`
precision highp float;
varying vec2 vUv;
uniform sampler2D uScene;
uniform sampler2D uBloom;
uniform vec2  uRes;
uniform float uDecode;
uniform float uPack;
uniform float uGlow;
uniform float uExposure;
uniform float uVignette;
uniform float uScrimDir;
uniform float uScrimAmt;
uniform float uSeed;

vec3 aces(vec3 x) {
  return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}

void main() {
  vec3 scene = texture2D(uScene, vUv).rgb;
  if (uDecode > 0.5) scene = scene / max(vec3(0.002), 1.0 - scene);
  vec3 bloom = texture2D(uBloom, vUv).rgb / uPack;

  vec3 c = scene + bloom * uGlow;
  c = aces(c * uExposure);
  c = pow(max(c, 0.0), vec3(0.4545));

  vec2 d = vUv - 0.5;
  c *= 1.0 - uVignette * dot(d, d) * 1.9;

  if (uScrimDir > 0.5) {
    float x = uScrimDir < 1.5 ? vUv.x
            : uScrimDir < 2.5 ? 1.0 - vUv.x
            : uScrimDir < 3.5 ? 1.0 - vUv.y
            : vUv.y;
    c *= 1.0 - uScrimAmt * pow(1.0 - clamp(x, 0.0, 1.0), 2.4);
  }

  float n = fract(sin(dot(gl_FragCoord.xy + uSeed, vec2(12.9898, 78.233))) * 43758.5453);
  c += (n - 0.5) / 255.0;

  gl_FragColor = vec4(c, 1.0);
}
`;var ft={distance:24,elevation:-5.5,azimuth:0,orbitSpeed:0,roll:-20,fov:42,diskInner:3,diskOuter:15,diskThickness:.26,diskDensity:1,brightness:1,spinSpeed:.06,grain:.48,doppler:.35,hotColor:"#FFF3DE",midColor:"#FFB36B",coolColor:"#8E3A0B",starBrightness:.5,glow:1,exposure:.9,vignette:.28,steps:300,resolution:.7,maxDpr:1.75,focus:[.72,.46],scrim:"none",scrimStrength:.9,paused:!1},Q=Math.PI/180;function be(f){let n=f.trim().replace("#",""),H=n.length===3?n[0]+n[0]+n[1]+n[1]+n[2]+n[2]:n.slice(0,6),c=parseInt(H,16);return[(c>>16&255)/255,(c>>8&255)/255,(c&255)/255].map(T=>T<=.04045?T/12.92:Math.pow((T+.055)/1.055,2.4))}function je(f,n,H){let c={...ft,...H},k=()=>{},T=new Promise(o=>{k=o}),F=null,Z=typeof window.matchMedia=="function"&&window.matchMedia("(prefers-reduced-motion: reduce)").matches,Te={alpha:!1,antialias:!1,depth:!1,stencil:!1,powerPreference:"high-performance",preserveDrawingBuffer:!1},e=n.getContext("webgl2",Te)||n.getContext("webgl",Te);function L(o){f.dataset.webgl=o,n.style.display="none",k(!1)}if(!e)return L("unsupported"),{cleanup:()=>{},ready:T};let Ee=e.getExtension("WEBGL_debug_renderer_info"),Qe=Ee?String(e.getParameter(Ee.UNMASKED_RENDERER_WEBGL)||""):"",ue=/swiftshader|llvmpipe|softpipe|software|microsoft basic/i.test(Qe),Re=typeof WebGL2RenderingContext!="undefined"&&e instanceof WebGL2RenderingContext;function _e(o,t){let r=e.createShader(o);return r?(e.shaderSource(r,t),e.compileShader(r),e.getShaderParameter(r,e.COMPILE_STATUS)?r:(console.error("blackhole: shader failed \u2014",e.getShaderInfoLog(r)||"no log (context lost?)"),e.deleteShader(r),null)):null}function z(o){let t=_e(e.VERTEX_SHADER,We),r=_e(e.FRAGMENT_SHADER,o);if(!t||!r)return null;let u=e.createProgram();if(!u)return null;if(e.attachShader(u,t),e.attachShader(u,r),e.bindAttribLocation(u,0,"aPos"),e.linkProgram(u),e.deleteShader(t),e.deleteShader(r),!e.getProgramParameter(u,e.LINK_STATUS))return console.error(e.getProgramInfoLog(u)),null;let l={},x=e.getProgramParameter(u,e.ACTIVE_UNIFORMS);for(let d=0;d<x;d++){let s=e.getActiveUniform(u,d);s&&(l[s.name]=e.getUniformLocation(u,s.name))}return{program:u,u:l}}let E=!0,$=e.UNSIGNED_BYTE,ae=e.RGBA;if(Re){let o=e;o.getExtension("EXT_color_buffer_half_float")||o.getExtension("EXT_color_buffer_float")?($=o.HALF_FLOAT,ae=o.RGBA16F):E=!1}else{let o=e.getExtension("OES_texture_half_float"),t=e.getExtension("EXT_color_buffer_half_float");o&&t?$=o.HALF_FLOAT_OES:E=!1}E||($=e.UNSIGNED_BYTE,ae=e.RGBA);let De=Re||!!e.getExtension("OES_texture_half_float_linear")||!E?e.LINEAR:e.NEAREST,Se=E?1:.12;function N(o,t){let r=e.createTexture(),u=e.createFramebuffer();if(!r||!u)return null;e.bindTexture(e.TEXTURE_2D,r),e.texImage2D(e.TEXTURE_2D,0,ae,o,t,0,e.RGBA,$,null),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MIN_FILTER,De),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MAG_FILTER,De),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_S,e.CLAMP_TO_EDGE),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_T,e.CLAMP_TO_EDGE),e.bindFramebuffer(e.FRAMEBUFFER,u),e.framebufferTexture2D(e.FRAMEBUFFER,e.COLOR_ATTACHMENT0,e.TEXTURE_2D,r,0);let l=e.checkFramebufferStatus(e.FRAMEBUFFER);return e.bindFramebuffer(e.FRAMEBUFFER,null),l!==e.FRAMEBUFFER_COMPLETE?(e.deleteTexture(r),e.deleteFramebuffer(u),null):{fb:u,tex:r,w:o,h:t}}let y=null,R=null,h=null,S=null,a=null,ee=null,v=null,_=null,p=null,m=null,g=null,W=0,X=0,Y=0,le=0,se=0;function Me(){return y=z(Xe),R=z(Ye),h=z(Ve),S=z(qe),a=z(Ke),!y||!R||!h||!S||!a?!1:(ee=e.createBuffer(),e.bindBuffer(e.ARRAY_BUFFER,ee),e.bufferData(e.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),e.STATIC_DRAW),e.enableVertexAttribArray(0),e.vertexAttribPointer(0,2,e.FLOAT,!1,0,0),e.disable(e.DEPTH_TEST),e.disable(e.BLEND),!0)}function Ae(){for(let o of[v,_,p,m,g])o&&(e.deleteTexture(o.tex),e.deleteFramebuffer(o.fb));v=null,_=null,p=null,m=null,g=null,W=0}function fe(){let o=f.getBoundingClientRect(),t=ue?1:Math.min(window.devicePixelRatio||1,Math.max(1,c.maxDpr)),r=Math.max(1,Math.round(o.width)),u=Math.max(1,Math.round(o.height)),l=ue?.34:Math.min(1,Math.max(.4,c.resolution)),x=Math.max(2,Math.round(r*t)),d=Math.max(2,Math.round(u*t)),s=Math.max(2,Math.round(x*l)),b=Math.max(2,Math.round(d*l));if(x===X&&d===Y&&s===le&&b===se)return!0;X=x,Y=d,le=s,se=b,n.width=x,n.height=d,n.style.width=r+"px",n.style.height=u+"px",Ae(),v=N(s,b),_=N(s,b),p=N(s,b);let A=Math.max(2,s>>2),C=Math.max(2,b>>2);return m=N(A,C),g=N(A,C),!!(v&&_&&p&&m&&g)}let ce=Z?6:0,V=0,q=!0,ke=!document.hidden,Fe=!0,M=0,me=!1;function te(){return ke&&Fe}function K(o,t){e.useProgram(o.program),e.bindFramebuffer(e.FRAMEBUFFER,t?t.fb:null),e.viewport(0,0,t?t.w:X,t?t.h:Y)}function j(){e.drawArrays(e.TRIANGLES,0,3)}function w(o,t){e.activeTexture(e.TEXTURE0+t),e.bindTexture(e.TEXTURE_2D,o)}let Le=[[.5,.333],[.25,.667],[.75,.111],[.125,.444],[.625,.778],[.375,.222],[.875,.556],[.0625,.889]];function ye(o){if(!y||!R||!h||!S||!a||!v||!_||!p||!m||!g)return;let t=c,r=(t.azimuth+t.orbitSpeed*o)*Q,u=Math.max(-88,Math.min(88,t.elevation))*Q,l=Math.max(2.2,t.distance),x=Math.cos(u),d=l*x*Math.cos(r),s=l*Math.sin(u),b=l*x*Math.sin(r),A=-d/l,C=-s/l,re=-b/l,U=re,B=0,I=-A,he=Math.hypot(U,B,I)||1;U/=he,B/=he,I/=he;let Ge=B*re-I*C,Oe=I*A-U*re,He=U*C-B*A,G=Math.cos(t.roll*Q),O=Math.sin(t.roll*Q),$e=U*G+Ge*O,et=B*G+Oe*O,tt=I*G+He*O,ot=-U*O+Ge*G,rt=-B*O+Oe*G,nt=-I*O+He*G,ve=be(t.hotColor),pe=be(t.midColor),ge=be(t.coolColor),ze=Math.max(t.diskInner+.5,t.diskOuter);K(y,v);let i=y.u;e.uniform2f(i.uRes,v.w,v.h),e.uniform1f(i.uTime,o),e.uniform3f(i.uCamPos,d,s,b),e.uniform3f(i.uRight,$e,et,tt),e.uniform3f(i.uUp,ot,rt,nt),e.uniform3f(i.uFwd,A,C,re),e.uniform1f(i.uTanHalf,Math.tan(Math.max(8,Math.min(110,t.fov))*.5*Q)),e.uniform2f(i.uFocus,t.focus[0],1-t.focus[1]),e.uniform1f(i.uSteps,ue?130:Math.max(60,Math.min(460,Math.round(t.steps)))),e.uniform1f(i.uSkyR,Math.max(l*1.35,ze*2.4)),e.uniform1f(i.uDiskIn,Math.max(1.05,t.diskInner)),e.uniform1f(i.uDiskOut,ze),e.uniform1f(i.uThick,Math.max(.02,t.diskThickness)),e.uniform1f(i.uDensity,Math.max(0,t.diskDensity)),e.uniform1f(i.uSpin,t.spinSpeed*6.2831853),e.uniform1f(i.uGrain,Math.max(.02,t.grain)),e.uniform1f(i.uBright,Math.max(0,t.brightness)),e.uniform1f(i.uDoppler,Math.max(0,Math.min(1,t.doppler))),e.uniform3f(i.uHot,ve[0],ve[1],ve[2]),e.uniform3f(i.uMid,pe[0],pe[1],pe[2]),e.uniform3f(i.uCool,ge[0],ge[1],ge[2]),e.uniform1f(i.uStars,Math.max(0,t.starBrightness)),e.uniform1f(i.uEncode,E?0:1);let Ne=Le[W%Le.length];e.uniform2f(i.uJitter,Ne[0]-.5,Ne[1]-.5),e.uniform1f(i.uSeed,W%64*17.13),j();let it=W===0?1:.14;K(R,p),w(v.tex,0),w(_.tex,1),e.uniform1i(R.u.uCur,0),e.uniform1i(R.u.uPrev,1),e.uniform1f(R.u.uAlpha,it),j();let ne=p,ut=_;_=p,p=ut,W++,K(h,m),w(ne.tex,0),e.uniform1i(h.u.uTex,0),e.uniform2f(h.u.uTexel,1/ne.w,1/ne.h),e.uniform1f(h.u.uDecode,E?0:1),e.uniform1f(h.u.uPack,Se),e.uniform1f(h.u.uThreshold,.85),j();let ie=(at,xe,lt,st)=>{K(S,xe),w(at.tex,0),e.uniform1i(S.u.uTex,0),e.uniform2f(S.u.uStep,lt/xe.w,st/xe.h),j()};ie(m,g,1,0),ie(g,m,0,1),ie(m,g,2.6,0),ie(g,m,0,2.6),K(a,null),w(ne.tex,0),w(m.tex,1),e.uniform1i(a.u.uScene,0),e.uniform1i(a.u.uBloom,1),e.uniform2f(a.u.uRes,X,Y),e.uniform1f(a.u.uDecode,E?0:1),e.uniform1f(a.u.uPack,Se),e.uniform1f(a.u.uGlow,Math.max(0,t.glow)*.26),e.uniform1f(a.u.uExposure,Math.max(.05,t.exposure)),e.uniform1f(a.u.uVignette,Math.max(0,Math.min(1,t.vignette))),e.uniform1f(a.u.uScrimDir,t.scrim==="left"?1:t.scrim==="right"?2:t.scrim==="top"?3:t.scrim==="bottom"?4:0),e.uniform1f(a.u.uScrimAmt,Math.max(0,Math.min(1,t.scrimStrength))),e.uniform1f(a.u.uSeed,o*60%1e3),j()}function J(o){for(let t=0;t<o;t++)ye(ce)}function D(){return c.paused||Z}function oe(){M&&cancelAnimationFrame(M),M=0,me=!0}function P(){!q||M||(me=!1,V=0,M=requestAnimationFrame(de))}function de(o){if(!q)return;if(!te()){M=requestAnimationFrame(de),V=o;return}if(D()){J(16),oe();return}M=requestAnimationFrame(de);let t=V?Math.min(.05,(o-V)/1e3):0;V=o,ce+=t,ye(ce)}if(!Me())return L("build-failed"),{cleanup:()=>{},ready:T};if(!fe())return L("framebuffer"),{cleanup:()=>{},ready:T};J(D()?16:1),k(!0),D()?me=!0:P();let we=new ResizeObserver(()=>{if(!fe()){L("framebuffer");return}D()?J(16):P()});we.observe(f);let Pe=new IntersectionObserver(o=>{var t,r;Fe=(r=(t=o[0])==null?void 0:t.isIntersecting)!=null?r:!0,te()&&!D()&&P()},{threshold:0});Pe.observe(f);let Ce=()=>{ke=!document.hidden,te()&&!D()&&P()},Ue=o=>{Z=o.matches,Z?(J(16),oe()):te()&&!c.paused&&P()};typeof window.matchMedia=="function"&&(F=window.matchMedia("(prefers-reduced-motion: reduce)"),typeof F.addEventListener=="function"&&F.addEventListener("change",Ue));let Be=o=>{o.preventDefault(),q=!1,oe(),n.style.display="none"},Ie=()=>{if(X=Y=le=se=0,!Me()){L("lost");return}if(n.style.display="",f.dataset.webgl="",!fe()){L("framebuffer");return}q=!0,J(D()?16:1),D()||P()};document.addEventListener("visibilitychange",Ce),n.addEventListener("webglcontextlost",Be),n.addEventListener("webglcontextrestored",Ie);function Ze(){q=!1,oe(),we.disconnect(),Pe.disconnect(),document.removeEventListener("visibilitychange",Ce),n.removeEventListener("webglcontextlost",Be),n.removeEventListener("webglcontextrestored",Ie),F&&typeof F.removeEventListener=="function"&&F.removeEventListener("change",Ue),Ae(),ee&&e.deleteBuffer(ee);for(let o of[y,R,h,S,a])o&&e.deleteProgram(o.program)}return{cleanup:Ze,ready:T}}function Je(){let f=document.getElementById("bh-host"),n=document.getElementById("bh-canvas");if(!f||!n)return;let H=window.__BLACKHOLE_OPTS__||{},{ready:c}=je(f,n,H);c.then(k=>{f.dataset.ready=k?"true":"false"})}document.readyState==="loading"?document.addEventListener("DOMContentLoaded",Je):Je();})();
