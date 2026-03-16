export const COLOR_MAP = {
  brown:    '#795548',
  lightBlue:'#4dd0e1',
  pink:     '#f06292',
  orange:   '#ff7043',
  red:      '#ef5350',
  yellow:   '#ffca28',
  green:    '#43a047',
  darkBlue: '#1565c0',
  railroad: '#37474f',
  utility:  '#607d8b',
};

// rent[0]=base, [1-4]=1-4 houses, [5]=hotel
// railroad rent[0-3] = 1-4 railroads owned
// houseCost = cost per house AND per hotel
export const BOARD_CELLS = [
  { pos:0,  type:'go',        name:'СТАРТ',           price:0,   colorGroup:null,      icon:'🚀' },
  { pos:1,  type:'street',    name:'Тверская',         price:60,  colorGroup:'brown',   rent:[2,10,30,90,160,250],     houseCost:50 },
  { pos:2,  type:'community', name:'Казна',            price:0,   colorGroup:null,      icon:'📦' },
  { pos:3,  type:'street',    name:'Арбат',            price:60,  colorGroup:'brown',   rent:[4,20,60,180,320,450],    houseCost:50 },
  { pos:4,  type:'tax',       name:'Налог',            price:0,   colorGroup:null,      tax:200, icon:'💸' },
  { pos:5,  type:'railroad',  name:'Казанский вкз.',   price:200, colorGroup:'railroad',rent:[25,50,100,200] },
  { pos:6,  type:'street',    name:'Невский пр.',      price:100, colorGroup:'lightBlue',rent:[6,30,90,270,400,550],   houseCost:50 },
  { pos:7,  type:'chance',    name:'Шанс',             price:0,   colorGroup:null,      icon:'❓' },
  { pos:8,  type:'street',    name:'Садовая ул.',      price:100, colorGroup:'lightBlue',rent:[6,30,90,270,400,550],   houseCost:50 },
  { pos:9,  type:'street',    name:'Кузнецкий мост',   price:120, colorGroup:'lightBlue',rent:[8,40,100,300,450,600],  houseCost:50 },
  { pos:10, type:'jail',      name:'Тюрьма',           price:0,   colorGroup:null,      icon:'🏛️' },
  { pos:11, type:'street',    name:'Остоженка',        price:140, colorGroup:'pink',    rent:[10,50,150,450,625,750],  houseCost:100 },
  { pos:12, type:'utility',   name:'Электростанция',   price:150, colorGroup:'utility', icon:'⚡' },
  { pos:13, type:'street',    name:'Пречистенка',      price:140, colorGroup:'pink',    rent:[10,50,150,450,625,750],  houseCost:100 },
  { pos:14, type:'street',    name:'Патриаршие пруды', price:160, colorGroup:'pink',    rent:[12,60,180,500,700,900],  houseCost:100 },
  { pos:15, type:'railroad',  name:'Ленинградский вкз.',price:200,colorGroup:'railroad',rent:[25,50,100,200] },
  { pos:16, type:'street',    name:'Бульварное кольцо',price:180, colorGroup:'orange',  rent:[14,70,200,550,750,950],  houseCost:100 },
  { pos:17, type:'community', name:'Казна',            price:0,   colorGroup:null,      icon:'📦' },
  { pos:18, type:'street',    name:'Садовое кольцо',   price:180, colorGroup:'orange',  rent:[14,70,200,550,750,950],  houseCost:100 },
  { pos:19, type:'street',    name:'Кутузовский пр.',  price:200, colorGroup:'orange',  rent:[16,80,220,600,800,1000], houseCost:100 },
  { pos:20, type:'parking',   name:'Парковка',         price:0,   colorGroup:null,      icon:'🅿️' },
  { pos:21, type:'street',    name:'Ленинский пр.',    price:220, colorGroup:'red',     rent:[18,90,250,700,875,1050], houseCost:150 },
  { pos:22, type:'chance',    name:'Шанс',             price:0,   colorGroup:null,      icon:'❓' },
  { pos:23, type:'street',    name:'Калининский пр.',  price:220, colorGroup:'red',     rent:[18,90,250,700,875,1050], houseCost:150 },
  { pos:24, type:'street',    name:'Новый Арбат',      price:240, colorGroup:'red',     rent:[20,100,300,750,925,1100],houseCost:150 },
  { pos:25, type:'railroad',  name:'Белорусский вкз.', price:200, colorGroup:'railroad',rent:[25,50,100,200] },
  { pos:26, type:'street',    name:'Проспект Мира',    price:260, colorGroup:'yellow',  rent:[22,110,330,800,975,1150],houseCost:150 },
  { pos:27, type:'street',    name:'Ярославское ш.',   price:260, colorGroup:'yellow',  rent:[22,110,330,800,975,1150],houseCost:150 },
  { pos:28, type:'utility',   name:'Водоканал',        price:150, colorGroup:'utility', icon:'💧' },
  { pos:29, type:'street',    name:'Рублёвка',         price:280, colorGroup:'yellow',  rent:[24,120,360,850,1025,1200],houseCost:150 },
  { pos:30, type:'goToJail',  name:'В тюрьму!',        price:0,   colorGroup:null,      icon:'👮' },
  { pos:31, type:'street',    name:'Кутузовка',        price:300, colorGroup:'green',   rent:[26,130,390,900,1100,1275],houseCost:200 },
  { pos:32, type:'street',    name:'Рублёвская ул.',   price:300, colorGroup:'green',   rent:[26,130,390,900,1100,1275],houseCost:200 },
  { pos:33, type:'community', name:'Казна',            price:0,   colorGroup:null,      icon:'📦' },
  { pos:34, type:'street',    name:'Серебряный бор',   price:320, colorGroup:'green',   rent:[28,150,450,1000,1200,1400],houseCost:200 },
  { pos:35, type:'railroad',  name:'Ярославский вкз.', price:200, colorGroup:'railroad',rent:[25,50,100,200] },
  { pos:36, type:'chance',    name:'Шанс',             price:0,   colorGroup:null,      icon:'❓' },
  { pos:37, type:'street',    name:'Москва-Сити',      price:350, colorGroup:'darkBlue',rent:[35,175,500,1100,1300,1500],houseCost:200 },
  { pos:38, type:'tax',       name:'Налог на роскошь', price:0,   colorGroup:null,      tax:75, icon:'💎' },
  { pos:39, type:'street',    name:'Рублёвский дворец',price:400, colorGroup:'darkBlue',rent:[50,200,600,1400,1700,2000],houseCost:200 },
];

// [gridCol, gridRow] 1-indexed for 11×11 grid
export const CELL_GRID = [
  [11,11],[10,11],[9,11],[8,11],[7,11],[6,11],[5,11],[4,11],[3,11],[2,11], // 0-9
  [1,11],                                                                   // 10
  [1,10],[1,9],[1,8],[1,7],[1,6],[1,5],[1,4],[1,3],[1,2],                  // 11-19
  [1,1],                                                                    // 20
  [2,1],[3,1],[4,1],[5,1],[6,1],[7,1],[8,1],[9,1],[10,1],                  // 21-29
  [11,1],                                                                   // 30
  [11,2],[11,3],[11,4],[11,5],[11,6],[11,7],[11,8],[11,9],[11,10],          // 31-39
];

// Side for each position: bottom | left | top | right
export const CELL_SIDE = [
  'bottom','bottom','bottom','bottom','bottom','bottom','bottom','bottom','bottom','bottom', // 0-9
  'corner',                                                                                   // 10
  'left','left','left','left','left','left','left','left','left',                            // 11-19
  'corner',                                                                                   // 20
  'top','top','top','top','top','top','top','top','top',                                    // 21-29
  'corner',                                                                                   // 30
  'right','right','right','right','right','right','right','right','right',                  // 31-39
];
