/*******************************************************************************

    uBlock Origin Lite - a comprehensive, MV3-compliant content blocker
    Copyright (C) 2014-present Raymond Hill

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see {http://www.gnu.org/licenses/}.

    Home: https://github.com/gorhill/uBlock
*/

/* jshint esversion:11 */

'use strict';

// ruleset: nor-0

/******************************************************************************/

// Important!
// Isolate from global scope
(function uBOL_cssProceduralImport() {

/******************************************************************************/

const argsList = [["{\"selector\":\".teaser__native\",\"tasks\":[[\"upward\",4]]}"],["{\"selector\":\"#grtvbelt_Sponsored\",\"tasks\":[[\"upward\",1]]}","{\"selector\":\".ad_interscroller\",\"tasks\":[[\"upward\",\".wrapper\"]]}"],["{\"selector\":\".js-betting-widget.is-country-no\",\"tasks\":[[\"upward\",2]]}"],["{\"selector\":\"a\",\"tasks\":[[\"has-text\",\"/[kc]as\\\\ino/i\"]]}"],["{\"selector\":\"p\",\"tasks\":[[\"has-text\",\"/^\\\\xA0$/\"]]}"],["{\"selector\":\"script[src^=\\\"//s1.adform.net\\\"]\",\"tasks\":[[\"upward\",2]]}"],["{\"selector\":\"p\",\"tasks\":[[\"has-text\",\"/cas\\\\ino/i\"]]}"],["{\"selector\":\"h2\",\"tasks\":[[\"has\",{\"selector\":\"+ p\",\"tasks\":[[\"has-text\",\"/cas\\\\ino/i\"]]}]]}"],["{\"selector\":\"section.elementor-top-section\",\"tasks\":[[\"has-text\",\"/\\\\s\\\\sAnnoncer?\\\\s\\\\s/i\"],[\"spath\",\" + section.elementor-top-section:has(.elementor-image > [loading=\\\"lazy\\\"])\"]]}","{\"selector\":\"section.elementor-top-section\",\"tasks\":[[\"has-text\",\"/\\\\s\\\\sAnnoncer?\\\\s\\\\s/i\"],[\"spath\",\":has(+ section.elementor-top-section .elementor-image > [loading=\\\"lazy\\\"])\"]]}"],["{\"selector\":\"a[href*=\\\"casino\\\"]\",\"tasks\":[[\"upward\",3]]}"],["{\"selector\":\"p\",\"tasks\":[[\"has-text\",\"/^\\\\xA0$/\"],[\"not\",{\"selector\":\"\",\"tasks\":[[\"has-text\",\"/\\\\S/\"]]}],[\"spath\",\":not(:has(img))\"]]}"],["{\"selector\":\"a[href*=\\\".bedrageri.com/\\\"]\",\"tasks\":[[\"upward\",2]]}"],["{\"selector\":\".section-1-ad\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\"div[id^=\\\"leftAdSpotAdcontainer\\\"]\",\"tasks\":[[\"upward\",2]]}"],["{\"selector\":\".elementor-widget-text-editor\",\"tasks\":[[\"has-text\",\"/\\\\s\\\\sANNONCER\\\\s\\\\s/\"]]}"],["{\"selector\":\".et_section_regular\",\"tasks\":[[\"has-text\",\"/cas\\\\ino/i\"]]}"],["{\"selector\":\".panel-latest-forum-threads\",\"tasks\":[[\"has-text\",\" sponsor\"]]}"],["{\"selector\":\"strong\",\"tasks\":[[\"has-text\",\"/Cas\\\\ino/i\"]]}"],["{\"selector\":\".boxbanner\",\"tasks\":[[\"upward\",2]]}"],["{\"selector\":\"#taboola-above-article-thumbnails\",\"tasks\":[[\"upward\",1]]}","{\"selector\":\".list-group\",\"tasks\":[[\"has-text\",\"/cas\\\\ino/i\"]]}"],["{\"selector\":\".adunit-lazy\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\".elementor-widget-wrap > .elementor-section\",\"tasks\":[[\"has-text\",\"REKLAMER\"]]}"],["{\"selector\":\".blog-post\",\"tasks\":[[\"has-text\",\"/cas\\\\ino/i\"]]}"],["{\"selector\":\".color-scheme-1\",\"tasks\":[[\"has-text\",\"/Cas\\\\ino/i\"],[\"spath\",\" + div\"]]}","{\"selector\":\".color-scheme-1\",\"tasks\":[[\"has-text\",\"/Cas\\\\ino/i\"]]}","{\"selector\":\"script[data-adfscript]\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\"h2\",\"tasks\":[[\"has-text\",\"/cas\\\\ino/i\"]]}"],["{\"selector\":\"div > .section\",\"tasks\":[[\"has\",{\"selector\":\"> div[class*=\\\"-label\\\"]\",\"tasks\":[[\"has-text\",\"Sponsored\"]]}]]}"],["{\"selector\":\"div[class*=\\\"advertisement-spot\\\"]\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\".ad-banner\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\".row div[class^=\\\"auglysing-\\\"]\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\".mvp-widget-home\",\"tasks\":[[\"has-text\",\"/^Velun{2}arar/\"]]}"],["{\"selector\":\".adsbygoogle\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\".g-10\",\"tasks\":[[\"has-text\",\"Artikkelen fortsetter \"]]}","{\"selector\":\".gofollow\",\"tasks\":[[\"upward\",3]]}"],["{\"selector\":\".wpb_wrapper\",\"tasks\":[[\"has-text\",\"/^An{2}onse:/\"]]}","{\"selector\":\"div[style^=\\\"font-size\\\"]\",\"tasks\":[[\"has-text\",\"/^An{2}onse:/\"]]}"],["{\"selector\":\"tr\",\"tasks\":[[\"has\",{\"selector\":\"td\",\"tasks\":[[\"has-text\",\"Annonse:\"]]}]]}"],["{\"selector\":\"div[id=\\\"336x280-sidebar\\\"]\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\"[data-variants*=\\\"article_netboard\\\"]\",\"tasks\":[[\"upward\",1]]}","{\"selector\":\"div[data-ad-subtype=\\\"in-feed\\\"]\",\"tasks\":[[\"upward\",2]]}"],["{\"selector\":\".lenkeboks\",\"tasks\":[[\"has-text\",\"/Cas\\\\ino/i\"]]}"],["{\"selector\":\".home-ads\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\"div[nf-desk-widget=\\\"spot.content\\\"]\",\"tasks\":[[\"upward\",2]]}"],["{\"selector\":\".adunit\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\"div[class^=\\\"css\\\"]\",\"tasks\":[[\"matches-css-before\",{\"name\":\"content\",\"pseudo\":\"before\",\"value\":\"^\\\"Annonse\\\"$\"}]]}"],["{\"selector\":\"[data-cy=\\\"video-page-horisontal\\\"] > div\",\"tasks\":[[\"has-text\",\"Annonse\"]]}"],["{\"selector\":\".container-footer-ad\",\"tasks\":[[\"upward\",1]]}","{\"selector\":\".sidebar-ad\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\"article ~ div\",\"tasks\":[[\"has-text\",\"/^A[n|ĳ]n\\\\ons/i\"]]}","{\"selector\":\"div[id^=\\\"brandboard\\\" i]\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\"div[data-placeholder=\\\"lantern_placeholder_ad\\\"]\",\"tasks\":[[\"upward\",2]]}"],["{\"selector\":\".preview\",\"tasks\":[[\"has\",{\"selector\":\".kicker\",\"tasks\":[[\"has-text\",\"/an{2}onse/i\"]]}]]}"],["{\"selector\":\"div[class^=\\\"adnun\\\"]\",\"tasks\":[[\"upward\",2]]}"],["{\"selector\":\".entrance\",\"tasks\":[[\"has\",{\"selector\":\".entrance__mark__text\",\"tasks\":[[\"has-text\",\"Annonse:\"]]}]]}","{\"selector\":\"div[data-name=\\\"gamer_toppbanner\\\"]\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\".bottomSmallSpaced.topMediumSpaced\",\"tasks\":[[\"has-text\",\"/^An{2}onse/\"]]}"],["{\"selector\":\".comcontent\",\"tasks\":[[\"upward\",1]]}","{\"selector\":\".item\",\"tasks\":[[\"has\",{\"selector\":\".meta\",\"tasks\":[[\"has-text\",\"/^An{2}onse$/\"]]}]]}","{\"selector\":\".td-c-loop-item\",\"tasks\":[[\"has\",{\"selector\":\".meta-info\",\"tasks\":[[\"has-text\",\"Annonse\"]]}]]}","{\"selector\":\"article\",\"tasks\":[[\"has\",{\"selector\":\".title\",\"tasks\":[[\"has-text\",\" – annonse\"]]}]]}","{\"selector\":\"article\",\"tasks\":[[\"has\",{\"selector\":\".title\",\"tasks\":[[\"has-text\",\"/[?:;—]\\\\san{2}ons[eø]r?$/\"]]}]]}"],["{\"selector\":\".latestnews-box\",\"tasks\":[[\"has-text\",\"/cas\\\\ino/i\"]]}"],["{\"selector\":\"div[id^=\\\"advert-\\\"]\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\".front optimus-element\",\"tasks\":[[\"has-text\",\"Eurojackpot\"]]}","{\"selector\":\"amedia-frontpage > .optimus-complex-front\",\"tasks\":[[\"has\",{\"selector\":\"> header > h2\",\"tasks\":[[\"has-text\",\"/Reklame|REKLAME/\"]]}]]}","{\"selector\":\"amedia-include[param-editionid=\\\"reklame\\\"]\",\"tasks\":[[\"upward\",1]]}","{\"selector\":\"article[data-lp-section=\\\"sportspill\\\"]:has(.slotHeader)\",\"tasks\":[[\"has-text\",\"/lot{2}o/i\"]]}"],["{\"selector\":\".adsbygoogle\",\"tasks\":[[\"upward\",2]]}","{\"selector\":\"ins[data-revive-zoneid]\",\"tasks\":[[\"upward\",2]]}"],["{\"selector\":\".textwidget\",\"tasks\":[[\"has-text\",\"Annonse\"]]}","{\"selector\":\".widget-title\",\"tasks\":[[\"has-text\",\"Annonser\"]]}"],["{\"selector\":\".widget\",\"tasks\":[[\"has-text\",\"Annonse\"]]}"],["{\"selector\":\".widget-goodpress-home-block-one\",\"tasks\":[[\"has-text\",\"Annonsørinnhold\"]]}"],["{\"selector\":\".widget\",\"tasks\":[[\"has-text\",\"Play-Asia\"]]}","{\"selector\":\".widget\",\"tasks\":[[\"has-text\",\"Reklame\"]]}"],["{\"selector\":\"iframe[src*=\\\"://ads.\\\"]\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\"div\",\"tasks\":[[\"has\",{\"selector\":\"> span\",\"tasks\":[[\"has-text\",\"Annonse\"]]}]]}"],["{\"selector\":\"div[data-ga-action$=\\\"_ad\\\"]\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\"#topboard\",\"tasks\":[[\"upward\",1]]}","{\"selector\":\"article > div\",\"tasks\":[[\"has-text\",\"/^an{2}onse$/\"]]}","{\"selector\":\"div\",\"tasks\":[[\"matches-css\",{\"name\":\"min-height\",\"value\":\"^165px$\"}]]}","{\"selector\":\"div.clearfix.col-full-width\",\"tasks\":[[\"has-text\",\"kommersielle partner\"]]}","{\"selector\":\"main > div > div\",\"tasks\":[[\"has-text\",\"kommersielle partner\"]]}","{\"selector\":\"main > section > section\",\"tasks\":[[\"has-text\",\"/^an{2}onse$/\"]]}","{\"selector\":\"section\",\"tasks\":[[\"has\",{\"selector\":\"> div > div\",\"tasks\":[[\"has-text\",\"/^an{2}onse$/\"]]}]]}"],["{\"selector\":\".one-half\",\"tasks\":[[\"has-text\",\"/[kc]as\\\\ino/i\"]]}"],["{\"selector\":\".adsbygoogle\",\"tasks\":[[\"upward\",5]]}"],["{\"selector\":\"div.large-12.row\",\"tasks\":[[\"has-text\",\"MASCUS\"]]}"],["{\"selector\":\".widget_media_image\",\"tasks\":[[\"has-text\",\"/^AN{2}ONSE/\"]]}"],["{\"selector\":\".fl-visible-desktop-medium\",\"tasks\":[[\"has\",{\"selector\":\"div[class^=\\\"ann-forside\\\"]\",\"tasks\":[[\"has-text\",\"/An{2}onse:/\"]]}]]}"],["{\"selector\":\".td-pb-span4\",\"tasks\":[[\"has-text\",\"ANNONSØRINNHOLD\"]]}"],["{\"selector\":\"div[id*=\\\"-feedAdvert\\\"]\",\"tasks\":[[\"upward\",1]]}"],["{\"selector\":\".forside_adholder\",\"tasks\":[[\"upward\",1]]}","{\"selector\":\"td\",\"tasks\":[[\"has-text\",\"/^\\\\xA0$/\"],[\"not\",{\"selector\":\"\",\"tasks\":[[\"has-text\",\"/\\\\S/\"]]}],[\"spath\",\":not(:has(img))\"]]}","{\"selector\":\"tr\",\"tasks\":[[\"has-text\",\"/^\\\\xA0$/\"],[\"not\",{\"selector\":\"\",\"tasks\":[[\"has-text\",\"/\\\\S/\"]]}],[\"spath\",\":not(:has(img))\"]]}"],["{\"selector\":\".col-md-3 .block\",\"tasks\":[[\"has-text\",\"ponsor\"]]}"]];

const hostnamesMap = new Map([["goal.com",2],["gunnarandreassen.com",3],["icelandreview.com",4],["knr.gl",4],["nutiminn.is",4],["bir.no",4],["medier24.no",4],["altomdata.dk",5],["anettelyskjaer.dk",[6,7]],["cuben-linedance.dk",6],["dreampapers.dk",[6,7]],["iphoneluppen.dk",[6,7]],["padleguide.dk",[6,24]],["polarmedia.dk",6],["nemsvar.nu",[6,7]],["baeredygtigtfiskeri.dk",8],["bilgalleri.dk",9],["check-in.dk",10],["dagens.dk",11],["dmi.dk",12],["edbpriser.dk",13],["fiskerforum.dk",14],["fodboldspilleren.dk",15],["gaming.dk",16],["jumpb.dk",17],["kanalfrederikshavn.dk",18],["kendte.dk",19],["lydogbillede.dk",20],["lydogbilde.no",20],["lystfiskerguiden.dk",21],["margit-henriksen.dk",22],["thura.dk",22],["ni.dk",23],["thelocal.dk",25],["thelocal.no",25],["bilasolur.is",26],["eidfaxi.is",27],["sporttv.is",28],["veitingageirinn.is",29],["sveip.net",30],["730.no",31],["arendalstidende.no",32],["bilnorge.no",33],["bimmers.no",34],["bt.no",35],["butikkoversikten.no",36],["byggenytt.no",37],["cw.no",38],["dagbladet.no",[39,40,41]],["sol.no",[39,41]],["elbil24.no",[41,45]],["kk.no",41],["seher.no",41],["vi.no",41],["dfly.no",42],["digi.no",43],["tu.no",43],["dn.no",44],["www.filmweb.no",46],["gamer.no",47],["glr.no",48],["itavisen.no",49],["leinstrand-il.no",50],["minmote.no",51],["nettavisen.no",52],["parcferme.no",53],["pengenytt.no",54],["politainment.no",55],["smis.no",55],["ranaposten.no",56],["xn--bodposten-n8a.no",56],["retrospilling.no",57],["skolediskusjon.no",58],["sorlandsavisen.no",59],["startsiden.no",60],["tek.no",61],["teknologia.no",62],["thaiguiden.no",63],["tungt.no",64],["tunnelsyn.no",65],["united.no",66],["utrop.no",67],["direkte.vg.no",68],["yrkesbil.no",69],["ipmsnorge.org",70]]);

const entitiesMap = new Map([["costume",0],["gamereactor",1]]);

const exceptionsMap = new Map(undefined);

self.proceduralImports = self.proceduralImports || [];
self.proceduralImports.push({ argsList, hostnamesMap, entitiesMap, exceptionsMap });

/******************************************************************************/

})();

/******************************************************************************/
