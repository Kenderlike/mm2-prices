--[[
    ОБФУСЦИРОВАННЫЙ СКРИПТ — РАБОЧАЯ ВЕРСИЯ
    Метод: замыкания + минификация имён + сокрытие логики
    Совместимость: Roblox Lua 5.1
]]

local function main()
    local a = game:GetService("HttpService")
    local b = game:GetService("CoreGui")
    local c = game:GetService("Players")
    local d = c.LocalPlayer
    
    local e = "https://raw.githubusercontent.com/Kenderlike/mm2-prices/refs/heads/main/prices.json"
    local f = {}
    local g = {}
    local h = {}
    local i = {}
    local j = false
    
    local k = {
        common = Color3.fromRGB(106,106,106),
        uncommon = Color3.fromRGB(0,255,255),
        rare = Color3.fromRGB(0,200,0),
        legendary = Color3.fromRGB(220,0,5),
        godly_chroma = Color3.fromRGB(255,0,179),
        vintage = Color3.fromRGB(230,200,0),
        ancient_evo = Color3.fromRGB(100,10,255)
    }
    
    local function l(m)
        local n = tostring(m):gsub("%s*%b()%s*$", "")
        return n:match("^%s*(.-)%s*$") or n
    end
    
    local function o(p)
        if i[p] then return i[p] end
        local q = l(p):lower()
        i[p] = q
        return q
    end
    
    local function r(s)
        if not s then return "unknown" end
        local t = "unknown"
        local u = math.huge
        for v,w in pairs(k) do
            local x = math.sqrt((s.R*255 - w.R*255)^2 + (s.G*255 - w.G*255)^2 + (s.B*255 - w.B*255)^2)
            if x < u then u = x; t = v end
        end
        if u < 15 then return t end
        return "unknown"
    end
    
    task.spawn(function()
        local y,z = pcall(function() return game:HttpGet(e) end)
        if y then
            local aa,ab = pcall(function() return a:JSONDecode(z) end)
            if aa and type(ab) == "table" then
                local function ac(ad)
                    for ae,af in pairs(ad) do
                        if type(af) == "table" then
                            local ag = false
                            for ah,_ in pairs(af) do
                                if k[ah] then ag = true; break end
                            end
                            if ag then
                                h[ae:lower()] = true
                                h[l(ae):lower()] = true
                                for ai,aj in pairs(af) do
                                    local ak = ae .. "_" .. ai
                                    f[ak] = aj
                                    g[ak:lower()] = aj
                                end
                            else
                                ac(af)
                            end
                        else
                            h[ae:lower()] = true
                            h[l(ae):lower()] = true
                            f[ae] = af
                            g[ae:lower()] = af
                        end
                    end
                end
                ac(ab)
                j = true
                print("✅ [MM2Calc] База загружена!")
            else
                warn("❌ [MM2Calc] Ошибка JSON")
            end
        else
            warn("❌ [MM2Calc] Ошибка HTTP")
        end
    end)
    
    if b:FindFirstChild("MM2TopCalc") then b.MM2TopCalc:Destroy() end
    
    local al = Instance.new("ScreenGui")
    al.Name = "MM2TopCalc"
    al.ResetOnSpawn = false
    al.Parent = b
    
    local am = Instance.new("Frame")
    am.Size = UDim2.new(0,400,0,100)
    am.Position = UDim2.new(0.5,-200,0,60)
    am.BackgroundTransparency = 1
    am.Visible = false
    am.Parent = al
    
    local an = Instance.new("TextLabel")
    an.Size = UDim2.new(1,0,0,40)
    an.BackgroundTransparency = 1
    an.Font = Enum.Font.GothamBlack
    an.TextSize = 30
    an.Text = "WAITING FOR TRADE..."
    an.TextColor3 = Color3.fromRGB(200,200,200)
    an.TextStrokeTransparency = 0
    an.Parent = am
    
    local ao = Instance.new("Frame")
    ao.Size = UDim2.new(1,0,0,50)
    ao.Position = UDim2.new(0,0,0,40)
    ao.BackgroundTransparency = 1
    ao.Parent = am
    
    local function ap(aq, ar, as)
        local at = Instance.new("TextLabel")
        at.Size = UDim2.new(0,120,0,40)
        at.Position = UDim2.new(aq,0,0,0)
        at.BackgroundColor3 = Color3.fromRGB(30,30,30)
        at.BackgroundTransparency = 0.3
        at.Font = Enum.Font.GothamBold
        at.TextSize = 24
        at.Text = ar
        at.TextColor3 = as
        at.Parent = ao
        Instance.new("UICorner", at).CornerRadius = UDim.new(0,8)
        return at
    end
    
    local au = ap(0, "0", Color3.fromRGB(46,204,113))
    local av = ap(0.35, "0", Color3.fromRGB(150,150,150))
    local aw = ap(0.7, "0", Color3.fromRGB(255,255,255))
    
    local function ax(ay, az)
        au.Text = tostring(ay)
        aw.Text = tostring(az)
        local ba = ay - az
        if ba > 10 then
            an.Text = "WIN"
            an.TextColor3 = Color3.fromRGB(46,204,113)
            av.Text = "+" .. ba
            av.TextColor3 = Color3.fromRGB(46,204,113)
        elseif ba < -10 then
            an.Text = "LOSE"
            an.TextColor3 = Color3.fromRGB(231,76,60)
            av.Text = tostring(ba)
            av.TextColor3 = Color3.fromRGB(231,76,60)
        else
            an.Text = "FAIR"
            an.TextColor3 = Color3.fromRGB(200,200,200)
            av.Text = (ba > 0 and "+" or "") .. ba
            av.TextColor3 = Color3.fromRGB(200,200,200)
        end
    end
    
    local function bb(bc, bd)
        if not bc or bc == "" then return nil end
        local be = l(bc)
        local bf = {be .. "_" .. bd, bc .. "_" .. bd, be .. "_unknown", be, bc}
        for _,bg in ipairs(bf) do
            if f[bg] ~= nil then return f[bg] end
            if g[bg:lower()] ~= nil then return g[bg:lower()] end
        end
        return nil
    end
    
    local function bh(bi, bj)
        local bk = bi.Parent
        if not bk then return end
        local bl = bk.Parent
        if not bl or not bl:IsA("GuiObject") or bl.AbsoluteSize.X > 350 or bl.AbsoluteSize.Y > 350 then
            bl = bk
        end
        local bm = bl:FindFirstChild("MM2_PriceTag")
        if not bm then
            bm = Instance.new("TextLabel")
            bm.Name = "MM2_PriceTag"
            bm.Size = UDim2.new(1,0,0,20)
            bm.Position = UDim2.new(0,0,0,0)
            bm.BackgroundTransparency = 1
            bm.TextStrokeTransparency = 0
            bm.TextSize = 16
            bm.Font = Enum.Font.GothamBlack
            bm.ZIndex = 100
            bm.BorderSizePixel = 0
            bm.Parent = bl
        end
        local bn, bo
        if type(bj) == "number" then
            bn = bj == 0 and "0" or tostring(bj)
            bo = bj == 0 and Color3.fromRGB(200,100,100) or Color3.fromRGB(46,204,113)
        elseif type(bj) == "string" then
            bn = bj
            bo = bj == "untradable" and Color3.fromRGB(150,150,150) or Color3.fromRGB(255,200,100)
        else
            if bm then bm:Destroy() end
            return
        end
        if bm.Text ~= bn then bm.Text = bn end
        if bm.TextColor3 ~= bo then bm.TextColor3 = bo end
    end
    
    local function bp(bq)
        local br = bq.Parent
        if br and br:IsA("GuiObject") and br.BackgroundTransparency < 1 then
            return r(br:IsA("Frame") and br.BackgroundColor3 or br.ImageColor3)
        end
        return "unknown"
    end
    
    local function bs(bt)
        local bu = 0
        if not bt then return bu end
        for _,bv in ipairs(bt:GetChildren()) do
            if bv:IsA("GuiObject") then
                for _,bw in ipairs(bv:GetDescendants()) do
                    if bw:IsA("TextLabel") and bw.Name ~= "MM2_PriceTag" then
                        local bx = bw.Text
                        if bx and #bx > 0 and #bx < 35 then
                            local by = o(bx)
                            if h[bx:lower()] or h[by] then
                                local bz = bp(bw)
                                local ca = bb(bx, bz)
                                if type(ca) == "number" then
                                    bu = bu + ca
                                    break
                                end
                            end
                        end
                    end
                end
            end
        end
        return bu
    end
    
    local cb = {}
    local cc = nil
    local cd = false
    
    local function ce()
        local cf = {}
        local cg = nil
        local ch = d:FindFirstChild("PlayerGui")
        if ch then
            for _,ci in ipairs(ch:GetChildren()) do
                if ci:IsA("ScreenGui") and ci.Enabled and ci.Name ~= "Chat" and ci.Name ~= "BubbleChat" and ci.Name ~= "PlayerList" then
                    local cj = ci:GetDescendants()
                    for ck,cl in ipairs(cj) do
                        if ck % 300 == 0 then task.wait() end
                        if cl:IsA("TextLabel") and cl.Name ~= "MM2_PriceTag" then
                            local cm = cl.Parent
                            if cm and (cm:IsA("Frame") or cm:IsA("ImageLabel") or cm:IsA("ImageButton")) then
                                table.insert(cf, cl)
                            end
                        end
                        if cl.Name == "Trade" and cl:IsA("GuiObject") and cl.Visible and cl:FindFirstChild("Player1") then
                            cg = cl
                        end
                    end
                end
            end
        end
        return cf, cg
    end
    
    task.spawn(function()
        while not j do task.wait(0.5) end
        while task.wait(0.5) do
            if not cd then
                task.spawn(function()
                    cd = true
                    local cn, co = ce()
                    cb = cn
                    cc = co
                    for _,cp in ipairs(cb) do
                        if cp.Parent then
                            local cq = cp.Text
                            if cq and #cq > 0 and #cq < 35 then
                                local cr = o(cq)
                                if h[cq:lower()] or h[cr] then
                                    local cs = bp(cp)
                                    local ct = bb(cq, cs)
                                    if ct ~= nil then
                                        bh(cp, ct)
                                    end
                                end
                            end
                        end
                    end
                    if cc and cc.Parent and cc.Visible then
                        am.Visible = true
                        local cu = cc:FindFirstChild("Player1") and cc.Player1:FindFirstChild("Offer")
                        local cv = cc:FindFirstChild("Player2") and cc.Player2:FindFirstChild("Offer")
                        ax(cu and bs(cu) or 0, cv and bs(cv) or 0)
                    else
                        am.Visible = false
                        ax(0, 0)
                    end
                    cd = false
                end)
            end
        end
    end)
end

main()
