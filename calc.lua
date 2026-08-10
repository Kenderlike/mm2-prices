local HttpService = game:GetService("HttpService")
local CoreGui = game:GetService("CoreGui")
local Players = game:GetService("Players")
local LocalPlayer = Players.LocalPlayer

-- === 1. БАЗА ЦЕН ===
local PRICES_URL = "https://raw.githubusercontent.com/Kenderlike/mm2-prices/refs/heads/main/prices.json"
local itemPrices = {}
local itemPricesLowerCase = {}  -- Для регистронезависимого поиска
local pricesLoaded = false

-- Цвета редкостей MM2 (RGB)
local RARITY_COLORS = {
    godlies   = Color3.fromRGB(255, 100, 255),  -- Розовый/фиолетовый
    chromas   = Color3.fromRGB(150, 255, 255),  -- Голубой/cyan
    ancients  = Color3.fromRGB(255, 200, 100),  -- Золотой
    vintages  = Color3.fromRGB(255, 255, 100),  -- Желтый
    legendaries = Color3.fromRGB(255, 50, 50),  -- Красный
    rares     = Color3.fromRGB(100, 150, 255),  -- Синий
    uncommons = Color3.fromRGB(100, 255, 100),  -- Зеленый
    commons   = Color3.fromRGB(200, 200, 200),  -- Серый
    collectibles = Color3.fromRGB(255, 150, 50), -- Оранжевый
    uniques   = Color3.fromRGB(200, 100, 255),  -- Фиолетовый
}

-- Функция определения редкости по цвету (RGB distance)
local function getRarityFromColor(color3)
    if not color3 then return nil end

    local minDistance = math.huge
    local closestRarity = nil

    for rarity, referenceColor in pairs(RARITY_COLORS) do
        -- Вычисляем евклидово расстояние между цветами
        local dr = (color3.R - referenceColor.R) * 255
        local dg = (color3.G - referenceColor.G) * 255
        local db = (color3.B - referenceColor.B) * 255
        local distance = math.sqrt(dr*dr + dg*dg + db*db)

        if distance < minDistance then
            minDistance = distance
            closestRarity = rarity
        end
    end

    return closestRarity
end

task.spawn(function()
    -- game:HttpGet работает в Xeno и большинстве других executor'ов
    local success, result = pcall(function()
        return game:HttpGet(PRICES_URL)
    end)
    if success then
        local ok, decoded = pcall(function() return HttpService:JSONDecode(result) end)
        if ok and type(decoded) == "table" then
            -- Рекурсивная функция для разворачивания с сохранением структуры
            local function flattenPrices(tbl, depth)
                depth = depth or 0
                for key, value in pairs(tbl) do
                    if type(value) == "table" and depth < 4 then
                        -- Проверяем, является ли это вложенной структурой с редкостями
                        local hasRarityKeys = false
                        for k, v in pairs(value) do
                            if type(k) == "string" and RARITY_COLORS[k] then
                                hasRarityKeys = true
                                break
                            end
                        end

                        if hasRarityKeys then
                            -- Это предмет с несколькими редкостями — сохраняем как есть
                            itemPrices[key] = value
                            itemPricesLowerCase[key:lower()] = value
                        else
                            -- Спускаемся глубже (категории типа "Оружие", "Ножи" и т.д.)
                            flattenPrices(value, depth + 1)
                        end
                    else
                        -- Если значение — цена (строка или число), сохраняем
                        itemPrices[key] = value
                        -- Также сохраняем в нижнем регистре для поиска
                        itemPricesLowerCase[key:lower()] = value
                    end
                end
            end

            flattenPrices(decoded)
            pricesLoaded = true
            print("✅ [MM2Calc] Цены загружены. Предметов:", (function() local n=0 for _ in pairs(itemPrices) do n=n+1 end return n end)())
        else
            warn("❌ [MM2Calc] Ошибка декодирования JSON:", decoded)
        end
    else
        warn("❌ [MM2Calc] Ошибка HTTP запроса:", result)
        warn("   Убедись что HTTP Requests включены в настройках игры (Game Settings > Security)")
    end
end)

-- === 2. ТАБЛО КАЛЬКУЛЯТОРА ===
if CoreGui:FindFirstChild("MM2TopCalc") then
    CoreGui.MM2TopCalc:Destroy()
end

local ScreenGui = Instance.new("ScreenGui")
ScreenGui.Name = "MM2TopCalc"
ScreenGui.ResetOnSpawn = false
ScreenGui.Parent = CoreGui

local TopContainer = Instance.new("Frame")
TopContainer.Size = UDim2.new(0, 400, 0, 100)
TopContainer.Position = UDim2.new(0.5, -200, 0, 60)
TopContainer.BackgroundTransparency = 1
TopContainer.Visible = false
TopContainer.Parent = ScreenGui

local StatusText = Instance.new("TextLabel")
StatusText.Size = UDim2.new(1, 0, 0, 40)
StatusText.BackgroundTransparency = 1
StatusText.Font = Enum.Font.GothamBlack
StatusText.TextSize = 30
StatusText.Text = "WAITING FOR TRADE..."
StatusText.TextColor3 = Color3.fromRGB(200, 200, 200)
StatusText.TextStrokeTransparency = 0
StatusText.Parent = TopContainer

local NumbersFrame = Instance.new("Frame")
NumbersFrame.Size = UDim2.new(1, 0, 0, 50)
NumbersFrame.Position = UDim2.new(0, 0, 0, 40)
NumbersFrame.BackgroundTransparency = 1
NumbersFrame.Parent = TopContainer

local function createValueBox(xPos, text, color)
    local box = Instance.new("TextLabel")
    box.Size = UDim2.new(0, 120, 0, 40)
    box.Position = UDim2.new(xPos, 0, 0, 0)
    box.BackgroundColor3 = Color3.fromRGB(30, 30, 30)
    box.BackgroundTransparency = 0.3
    box.Font = Enum.Font.GothamBold
    box.TextSize = 24
    box.Text = text
    box.TextColor3 = color
    box.Parent = NumbersFrame

    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, 8)
    corner.Parent = box
    return box
end

local MyValueBox    = createValueBox(0,    "0", Color3.fromRGB(46, 204, 113))
local DiffValueBox  = createValueBox(0.35, "0", Color3.fromRGB(150, 150, 150))
local TheirValueBox = createValueBox(0.7,  "0", Color3.fromRGB(255, 255, 255))

local function UpdateCalc(myTotal, theirTotal)
    MyValueBox.Text    = tostring(myTotal)
    TheirValueBox.Text = tostring(theirTotal)

    local diff = myTotal - theirTotal

    if diff > 10 then
        StatusText.Text       = "WIN"
        StatusText.TextColor3 = Color3.fromRGB(46, 204, 113)
        DiffValueBox.Text       = "+" .. tostring(diff)
        DiffValueBox.TextColor3 = Color3.fromRGB(46, 204, 113)
    elseif diff < -10 then
        StatusText.Text       = "LOSE"
        StatusText.TextColor3 = Color3.fromRGB(231, 76, 60)
        DiffValueBox.Text       = tostring(diff)
        DiffValueBox.TextColor3 = Color3.fromRGB(231, 76, 60)
    else
        StatusText.Text       = "FAIR"
        StatusText.TextColor3 = Color3.fromRGB(200, 200, 200)
        DiffValueBox.Text       = (diff > 0 and "+" or "") .. tostring(diff)
        DiffValueBox.TextColor3 = Color3.fromRGB(200, 200, 200)
    end
end

-- === 3. ПОДСЧЕТ И ЦЕННИКИ ===

-- Убирает суффикс в скобках: "Palms (Gun)" -> "Palms"
-- Также пробует полное имя если сокращённое не найдено
local function cleanName(name)
    return (name:gsub("%s*%b()%s*$", ""):match("^%s*(.-)%s*$"))
end

-- Возвращает цену с учётом редкости: число, строку ("x4 T1 Legendaries", "untradable"), или nil
-- Если предмет имеет несколько редкостей, использует rarity для выбора правильной цены
local function getPrice(rawName, rarity)
    if not rawName or rawName == "" then return nil end
    local name = cleanName(rawName)

    -- Сначала пробуем очищенное имя (точное совпадение)
    local price = itemPrices[name]
    if price == nil then
        -- Пробуем оригинальное имя
        price = itemPrices[rawName]
    end
    if price == nil then
        -- Регистронезависимый поиск
        local nameLower = name:lower()
        price = itemPricesLowerCase[nameLower]
        if price == nil then
            local rawNameLower = rawName:lower()
            price = itemPricesLowerCase[rawNameLower]
        end
    end

    if price == nil then return nil end

    -- Если цена — это таблица с редкостями, выбираем нужную
    if type(price) == "table" then
        if rarity and price[rarity] then
            return price[rarity]
        end
        -- Если редкость не найдена, берём первое доступное значение
        for _, value in pairs(price) do
            return value
        end
        return nil
    end

    -- Обычная цена (число или строка)
    return price
end

-- Числовое значение для суммирования в трейде
local function getNumericPrice(rawName, rarity)
    local price = getPrice(rawName, rarity)
    if type(price) == "number" then return price end
    return 0
end

-- Обновляет или создаёт ценник на карточке (В САМОМ ВЕРХУ, над карточкой)
-- parentFrame должен иметь BackgroundColor3 для определения редкости
local function updatePriceTag(parentFrame, rawName)
    if not rawName or rawName == "" then return end

    -- Получаем цвет фона карточки для определения редкости
    local bgColor = parentFrame.BackgroundColor3
    local rarity = getRarityFromColor(bgColor)
    local price = getPrice(rawName, rarity)

    local tag = parentFrame:FindFirstChild("MM2_PriceTag")
    if not tag then
        tag = Instance.new("TextLabel")
        tag.Name = "MM2_PriceTag"
        tag.Size = UDim2.new(1, 0, 0, 20)
        tag.Position = UDim2.new(0, 0, 0, -20)  -- НАД карточкой (отрицательное смещение)
        tag.BackgroundColor3 = Color3.fromRGB(0, 0, 0)
        tag.BackgroundTransparency = 0.3
        tag.TextSize = 16
        tag.Font = Enum.Font.GothamBlack
        tag.ZIndex = 100
        tag.BorderSizePixel = 0
        tag.Parent = parentFrame
    end

    if type(price) == "number" then
        -- Числовая цена
        if price == 0 then
            tag.Text       = "0"
            tag.TextColor3 = Color3.fromRGB(200, 100, 100)
        else
            tag.Text       = tostring(price)
            tag.TextColor3 = Color3.fromRGB(46, 204, 113)
        end
    elseif type(price) == "string" then
        -- Строковая цена: "untradable", "x4 T1"
        if price == "untradable" then
            tag.Text       = "untradable"
            tag.TextColor3 = Color3.fromRGB(150, 150, 150)
        else
            -- Прочие строки (например "x4 T1")
            tag.Text       = price
            tag.TextColor3 = Color3.fromRGB(255, 200, 100)
        end
    else
        -- nil или неизвестный тип — не показываем ценник
        if tag then tag:Destroy() end
    end
end

local function calculateOffer(container)
    local total = 0
    for _, slot in pairs(container:GetChildren()) do
        if slot:IsA("Frame") or slot:IsA("ImageLabel") or slot:IsA("ImageButton") then
            -- Получаем цвет фона для определения редкости
            local bgColor = slot.BackgroundColor3
            local rarity = getRarityFromColor(bgColor)

            for _, element in pairs(slot:GetDescendants()) do
                if element:IsA("TextLabel") and element.Name ~= "MM2_PriceTag" then
                    local price = getPrice(element.Text, rarity)
                    if price ~= nil then
                        total = total + getNumericPrice(element.Text, rarity)
                        break
                    end
                end
            end
        end
    end
    return total
end

-- === 4. ГЛАВНЫЙ ЦИКЛ ===
task.spawn(function()
    -- Ждём загрузки цен перед стартом (макс 10 секунд)
    local waited = 0
    while not pricesLoaded and waited < 10 do
        task.wait(0.5)
        waited = waited + 0.5
    end

    if not pricesLoaded then
        warn("⚠️ [MM2Calc] Цены не загрузились за 10 секунд. Ценники работать не будут.")
        warn("   Проверь: 1) HTTP Requests включены  2) URL доступен  3) Нет ошибок выше")
    end

    -- Отладка структуры GUI (один раз при старте)
    local PlayerGui = LocalPlayer:WaitForChild("PlayerGui", 10)
    if PlayerGui then
        local MainGUI = PlayerGui:FindFirstChild("MainGUI")
        if MainGUI then
            print("✅ [MM2Calc] MainGUI найден")
        else
            -- Перебираем все GUI чтобы найти правильное имя
            local guiNames = {}
            for _, child in pairs(PlayerGui:GetChildren()) do
                table.insert(guiNames, child.Name)
            end
            warn("⚠️ [MM2Calc] MainGUI не найден. Доступные GUI: " .. table.concat(guiNames, ", "))
        end
    end

    while task.wait(0.5) do
        pcall(function()
            local PlayerGui = LocalPlayer:FindFirstChild("PlayerGui")
            if not PlayerGui then return end

            -- 1. РИСУЕМ/ОБНОВЛЯЕМ ЦЕННИКИ (Инвентарь + Трейд)
            for _, element in pairs(PlayerGui:GetDescendants()) do
                if element:IsA("TextLabel") and element.Name ~= "MM2_PriceTag" then
                    local itemName = element.Text
                    if itemName and itemName ~= "" then
                        local parentFrame = element.Parent
                        if parentFrame and (parentFrame:IsA("Frame") or parentFrame:IsA("ImageLabel") or parentFrame:IsA("ImageButton")) then
                            -- Получаем цвет фона и определяем редкость
                            local bgColor = parentFrame.BackgroundColor3
                            local rarity = getRarityFromColor(bgColor)
                            local price = getPrice(itemName, rarity)

                            if price ~= nil then
                                updatePriceTag(parentFrame, itemName)
                            end
                        end
                    end
                end
            end

            -- 2. ЛОГИКА КАЛЬКУЛЯТОРА ТРЕЙДА
            local TradeUI = nil
            local MainGUI = PlayerGui:FindFirstChild("MainGUI")
            if MainGUI then
                for _, child in pairs(MainGUI:GetDescendants()) do
                    if child.Name == "Trade" and child:IsA("Frame") and child.Visible then
                        TradeUI = child
                        break
                    end
                end
            end

            if TradeUI then
                TopContainer.Visible = true

                local myOffer    = TradeUI:FindFirstChild("Player1") and TradeUI.Player1:FindFirstChild("Offer")
                local theirOffer = TradeUI:FindFirstChild("Player2") and TradeUI.Player2:FindFirstChild("Offer")

                local myTotal    = myOffer    and calculateOffer(myOffer)    or 0
                local theirTotal = theirOffer and calculateOffer(theirOffer) or 0

                UpdateCalc(myTotal, theirTotal)
            else
                TopContainer.Visible = false
                UpdateCalc(0, 0)
            end
        end)
    end
end)
